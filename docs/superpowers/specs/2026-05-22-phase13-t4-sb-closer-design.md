# Phase 13 T4.SB — Closer Brainstorming Spec

**Date:** 2026-05-22
**Branch:** `phase13-t4-sb-brainstorming`
**Baseline:** main HEAD `e75f743`
**Phase 13 sub-bundle count at dispatch:** 11 of 11 SHIPPED; T4.SB closes Phase 13 to **12 of 12 / FULLY CLOSED**.
**Workflow:** `copowers:brainstorming` (wraps `superpowers:brainstorming` with adversarial Codex review)
**Dispatch brief:** `docs/phase13-t4-sb-brainstorming-dispatch-brief.md`
**Substrate (PRIMARY):** `docs/phase3e-todo.md:11-101` — 7 operator-confirmed triage items (5-field-template; operator-verbatim framings).

---

## §A Status and scope

### §A.1 Closure framing

T4.SB is the **Phase 13 closer**. It does NOT introduce a new Theme — Phase 13 main spec §7.3 reserved T4.SB scope for the "verbatim operator usability list amended in place." The operator has supplied that list as 7 items (Items 1-7 at `docs/phase3e-todo.md:15-101`). Q4 close-tracking-flag schema already landed in v20 per main spec §7.2 line 986 LOCK + migration `0020_phase13_charts_patterns_autofill_usability.sql:262-307`; T4.SB scope is **Theme 4 usability + zero new Schema work** unless investigation surfaces absolute necessity.

### §A.2 Operator-confirmed severity table (per `docs/phase3e-todo.md` 5-field-template)

| Item | Title | Severity | Investigation needed? | Architectural decision? | Cosmetic/UX only? |
|---|---|---|---|---|---|
| 1 | 0 A+ candidates diagnostic (63 eval_runs since v20) | **HIGH** | YES (instrument `bucket_for`; capture blocking-criterion distribution) | YES (may surface threshold-loosening proposals) | No |
| 2 | Path A labeler subagent contract widening (`rule_criteria` + `narrative` keys) | Medium | NO (architectural; emit-contract change) | YES (coupled with Item 1 fix outcome) | No |
| 3 | Market-weather chart volume-axis noise (strip 0/1/1e8 y-tick labels) | Cosmetic | NO | NO | YES |
| 4 | Lightning glyph on watchlist offsets thumbnails (delete) | Cosmetic/UX | NO | NO | YES |
| 5 | Chart scope too narrow + JIT-vs-flat-file architectural Q | Medium | NO (orchestrator recommendation REVISED to JIT-primary) | YES (cache architecture + retention policy) | No |
| 6 | Watchlist expand-then-collapse loses thumbnail | UX | NO (canonical HTMX-OOB-swap gotcha applies) | NO | Almost-yes (1-route fix) |
| 7 | Metrics wiring audit + hyp-progress=0 specific defect | **HIGH** | YES (instrument `build_hypothesis_progress_card_vm` cohort lookup; enumerate ALL metric surfaces) | NO (fix-the-wiring + canonicalization-at-persistence) | No |

### §A.3 Strict NON-scope (cited explicitly to prevent scope creep)

- **Phase 14** (operator-defined; pending). T4.SB SHIPPED transitions Phase 13 to FULLY CLOSED; Phase 14 dispatch is a separate decision.
- **Research-branch advancement.** Item 1 diagnostic OUTPUT feeds `research/phase-0-tasks.md` "Later (deferred)" first-method-record selection — but research-branch authoring itself is NOT in T4.SB scope per V2.1 §V branch posture.
- **Schema changes.** v21 trades-backlinks already landed at T2.SB6c T-A.6c.1. T4.SB should NOT propose schema changes unless investigation surfaces an absolute necessity (e.g., a retention-policy table; §B.5 OQs surface the decision).
- **ZERO new Schwab API calls** (Phase 13 arc L2 LOCK preserved).
- **Re-opening V2 candidates banked at T2.SB6c return report §4.1** — most preserved as V2-banked. T4.SB MAY close Item 7 broader-audit-implied false-zero candidates (row 1 outcome-distribution surrogate; row 5 market_weather literal `trend_template_state="stage_2"`) IF investigation surfaces evidence at low marginal cost.

### §A.4 Cross-branch dependency (acknowledged, not pursued)

`research/phase-0-tasks.md` "Later (deferred)" enumerates 8 candidate A+-like indicators surveyed 2026-05-22 PM for the first-method-record selection. **Item 1 diagnostic output IS the input gating that selection.** T4.SB spec acknowledges this; T4.SB does NOT pre-commit to a research outcome. Concretely: Item 1 diagnostic emits a per-criterion blocking distribution; if (a) calibration miss confirmed, a threshold-loosening cfg-policy proposal may be banked V2; if (b) market-output confirmed, the diagnostic itself is the cycle-checklist artifact + research-branch is free to pick any of the 8 candidates.

---

## §B Per-item investigation and design

This section is the binding scope substrate for the writing-plans phase. Each item enumerates: (i) what to investigate (if any); (ii) what design decisions need locking; (iii) which code surfaces are touched; (iv) what discriminating tests pin behavior; (v) what V2 dependencies are banked.

### §B.1 Item 1 — 0 A+ candidates diagnostic (HIGH)

**Operator framing (verbatim):** "Purpose is to enter trades and make profit. No candidates = no trades. Conservative answer, but does not meet mission (ships are designed to go to sea...)."

**Production state confirmed by code reading:**
- `bucket_for` at `swing/evaluation/scoring.py:13-39` gates by (risk hard-filter) → (trend-template passes + allowed-miss) → (VCP fail count). `vcp_fails == 0` → `aplus`; `1 <= vcp_fails <= 2` → `watch`; `>= 3` → `skip`.
- `_step_evaluate` writes per-candidate rows to `candidates` table with `bucket` ∈ {aplus, watch, skip, excluded, error}; downstream surfaces (hyp-rec table; chart_renders `hyprec_detail` at `swing/pipeline/runner.py:2371`) gate on `bucket == 'aplus'`.
- **0 A+ across 63 eval_runs** since v20 detector chain landed: operator's confirmation at 2026-05-22 PM gate. Sub-A+ rows (`bucket == 'watch'`) populate hyp-rec card; A+ pipeline is structurally empty.

**Investigation design:**

The diagnostic answers: "of the per-eval-run candidate rows that landed in `bucket == 'watch'` or `bucket == 'skip'`, what is the distribution of failing criteria that prevent promotion to `aplus`?" This is the **per-criterion blocking distribution** + (where possible) a per-criterion **margin-of-failure** breakdown.

**Data source LOCK (per Codex R1 M#1 closure):** the diagnostic reads PERSISTED `candidate_criteria` rows (one row per `(candidate_id, criterion_name)` per migration `0001_phase1_initial.sql:48-56` — columns `result` IN ('pass','fail','na'), `value` TEXT, `rule` TEXT). The diagnostic does NOT re-run criteria against original OHLCV snapshots — that data is not persisted at all (`candidates` stores derived fields like `adr_pct` / `tight_streak` / `pullback_pct` but NOT the bar-level inputs to each criterion). Re-running would require OHLCV cache reconstruction at the relevant `data_asof_date` per candidate, which is V2 scope (OHLCV cache likely has many of the needed bars via `read_or_fetch_archive` BUT cross-day cache validity is not guaranteed). V1 scope: consume `candidate_criteria` directly.

**Diagnostic instrument** (NEW CLI subcommand; lives under production `swing/`):
- Subcommand: `swing diagnose aplus-blockers --eval-runs LAST_N` (default N=20; max N=100; covers operator's "63 eval_runs" window with operator-tunable scope).
- Reads `candidate_criteria` rows JOINed to `candidates` for the LAST_N `evaluation_runs`; aggregates per-criterion failure distribution across `bucket != 'aplus'` candidates.
- **Margin-of-failure derivation V1**: `candidate_criteria.value` is a free-text TEXT column; many criteria store numeric values as strings (e.g., `value='14.2'`); others store enum strings (e.g., `value='stage_2'`). The diagnostic parses `value` as float when possible + computes margin against the criterion's `rule` (also TEXT; e.g., `rule='value >= 70'`). When parsing fails (non-numeric criterion), the diagnostic emits "boolean-fail" with no margin. V2 candidate: structured `(criterion_value_numeric, criterion_threshold_numeric)` columns OR a parsing helper that knows each criterion's rule schema.
- Output: deterministic markdown table written to `exports/diagnostics/aplus-blockers-<ISO>.md` PLUS a CSV sidecar `exports/diagnostics/aplus-blockers-<ISO>.csv` for downstream analysis.
- Output schema (per-criterion-blocker row): `criterion_name`, `layer` (trend_template / vcp / risk per `candidate_criteria.layer`), `failed_count`, `na_count`, `failed_pct`, `mean_margin` (None when non-numeric), `median_margin`, `p90_margin`, `tickers_sample` (top-3 highest-margin tickers as comma-separated CSV cell).
- ASCII-only output (Windows cp1252 stdout safety per existing gotcha).

**Why CLI subcommand (vs. fold into pipeline step output OR fold into research branch):**
- Pipeline step output would couple operator workflow ("run pipeline" → "wait" → "read diagnostic") which is heavy-weight; CLI subcommand is fast (re-evaluates from persisted rows; no fresh data fetch).
- Research-branch authoring is V2.1 §V-governed; the diagnostic instrument is OPERATIONAL (production-grade audit tool) AND its output feeds research selection. Splitting CLI from research-branch document is correct: CLI in `swing/`; analysis writeup in `research/notes/` separately.
- The diagnostic is operationally durable — operator may re-run after threshold-loosening lands to verify drift.

**Code surfaces touched:**
- NEW module `swing/diagnostics/aplus_blockers.py` (pure-function analysis; ~150 LOC).
- NEW CLI subcommand `swing/cli.py:diagnose_aplus_blockers` (Click subcommand registered under existing `swing` entry point).
- Read-only against `candidates` + `candidate_criteria` + `evaluation_runs`; ZERO writes.
- Re-uses `swing/evaluation/scoring.py:bucket_for` ONLY as documentation of the gating order (the diagnostic itself does NOT invoke `bucket_for`; it consumes the already-persisted `bucket` column + `candidate_criteria` rows).

**Discriminating tests:**
- Plant a fixture eval_run with 5 candidates (1 aplus + 2 watch with `candidate_criteria` failing tt5+tt8 + 2 skip with `candidate_criteria` failing risk_size) + invoke diagnostic; assert per-criterion failed_count + failed_pct match planted distribution.
- Plant a fixture with all-aplus → diagnostic reports "no blockers (all aplus)".
- Plant a fixture with `candidate_criteria.result='na'` for one criterion → assert "NA" reported as `na_count` (separate from `failed_count`), NOT folded.
- Plant a fixture with non-numeric `candidate_criteria.value` (e.g., `'stage_2'`) → assert `mean_margin = None` + criterion reported as "boolean-fail" semantic.
- Plant a fixture with numeric `candidate_criteria.value` + parseable `rule` (e.g., `value='62.3'` + `rule='rs_rank >= 70'`) → assert margin computed correctly (62.3 - 70 = -7.7).
- ASCII-only stdout assertion (subprocess invocation per Windows-stdout-encoding lesson).

**Architectural decisions:**
- **Diagnostic instrument lives in production (`swing/`).** Operational utility justifies it. Cross-cuts research branch only via the OUTPUT file (markdown report consumed by research-branch first-method-record selection).
- **Diagnostic does NOT propose code changes.** Output is data + analysis; threshold-loosening proposals are operator-driven post-diagnostic-read (V2 / cfg-policy proposals; banked separately).

**V2 dependencies banked:**
- Threshold-loosening cfg-policy proposals (`cfg.trend_template.allowed_miss_names` widening; `cfg.vcp.acceptable_fail_count` if introduced). V2 because requires operator-paired triage on diagnostic output.
- Margin-of-failure semantics for NON-numeric criteria (e.g., `trend_template_close_above_ma200` is boolean). V1 reports as "boolean-fail" with no margin; V2 may add a richer fail-reason taxonomy.

### §B.2 Item 2 — Path A labeler subagent contract widening (Medium)

**Operator framing (verbatim):** "Similar to 1. Potentially too limiting, making it more difficult to identify good entry opportunities."

**Production state confirmed by code reading (per Codex R1 M#5 + M#6 closure):**
- `SilverLabelResponse` dataclass at `swing/patterns/labeling.py:143-178` ALREADY has 4 fields: `evaluation` + `confidence` + `structural_evidence_json` + `geometric_evidence_narrative` (mandatory ASCII-only narrative).
- `fire_claude_silver_label` at `swing/patterns/labeling.py:294-298` ALREADY persists `geometric_evidence_narrative` into the `labeler_evidence_json` envelope (key: `"geometric_evidence_narrative"`).
- Subagent prompt at `.claude/agents/pattern-labeler.md` ALREADY emits `geometric_evidence_narrative` per the existing contract.
- `/patterns/exemplars` enhanced-rendering template at `swing/web/templates/patterns/exemplars.html.j2:33-90` ALREADY renders `render.criterion_rows` (table at lines 51-78) + `render.narrative_text` (paragraph at lines 79-87). The "(no rule_criteria payload available)" + "(no narrative payload available)" placeholders fire when the VM-construction-time parse of `labeler_evidence_json` DOES NOT find those keys.
- T2.SB6c §1.5.2 Path C backfill script lands at `swing/cli.py:patterns_exemplars_backfill_labeler_evidence`. Path C is effective no-op against the 34 hand-labeled corpus rows because all 34 carry `geometric_score_json IS NULL` (S11 backfill execution observed `Augmented: 0; Skipped: 34`).
- **Gap location LOCK**: the missing data is at the EMITTER (subagent contract DOES NOT emit `rule_criteria`) + PERSISTENCE (`fire_claude_silver_label` does NOT add it to `labeler_evidence_json`) + VM-CONSTRUCTION (the VM builder for `/patterns/exemplars` does NOT extract `rule_criteria` from `labeler_evidence_json`). The TEMPLATE itself is correct + does NOT need extension.

**Investigation: NONE.** This is an emitter-contract widening with known-shape inputs/outputs. Coupling to Item 1: while 0 A+ persists, fresh exemplars do not accumulate organically; Path A widening is the only realistic unblock path.

**Design:**

The contract widening is **ADDITIVE for `rule_criteria` ONLY** — the existing `geometric_evidence_narrative` field is PRESERVED verbatim + does NOT rename. (The brief proposed "two new keys `rule_criteria` + `narrative`"; Codex R1 M#5 caught that "narrative" is already named `geometric_evidence_narrative` per the existing contract. To avoid contract migration cost on the 34 existing rows + cassette tests, we keep the existing field name.)

NEW emission key `rule_criteria` — array of per-rule pass/fail objects. Schema: `{ rule_name: str, passed: bool, threshold: float|str|null, observed: float|str|null, margin: float|null, narrative: str|null }`. One element per criterion the labeler evaluated (mirrors per-pattern-class criterion list at `swing/patterns/<pattern_class>.py` detector).

**Code surfaces touched (per Codex R1 M#6 closure — TEMPLATE NOT TOUCHED):**
- Subagent prompt at `.claude/agents/pattern-labeler.md`: extend emit contract with `rule_criteria` array; provide example JSON for each of the 5 V1 pattern classes (vcp / flat_base / cup_with_handle / high_tight_flag / double_bottom_w).
- `SilverLabelResponse` dataclass extension: add NEW `rule_criteria: list[dict] | None = None` field (default None for backward-compat with existing tests + cassettes); `__post_init__` validation per existing `Literal[...]` runtime-enforcement gotcha (validate each element is a dict with required keys `rule_name` + `passed`; defensive against malformed subagent output).
- `swing/cli.py:patterns_label_silver` + `swing/patterns/labeling.py:_fire_claude_silver_label`: parse + validate the new key from subagent JSON; pass through to dataclass construction.
- `fire_claude_silver_label` at labeling.py:294-298: extend the dict literal that builds `labeler_evidence_json` to include `"rule_criteria": response.rule_criteria` (when non-None; omit key entirely when None for backward-compat with existing rows).
- **VM-construction-time extension at `/patterns/exemplars` VM builder** (file path discovered at writing-plans phase via grep `exemplar_renders` definition): the existing VM emits `criterion_rows` per-exemplar; extend the VM builder to populate `criterion_rows` from `labeler_evidence_json['rule_criteria']` when present (currently the field is likely populated from a different source or stub-empty). Discriminating test asserts a fresh silver-label invocation emits `rule_criteria` + the VM renders the criterion rows table for that exemplar.
- **No schema change** (`labeler_evidence_json` is a JSON BLOB column).
- **No template change** (template already renders `criterion_rows` + `narrative_text`).

**Re-label vs forward-only decision (OQ-2.2):**

Two-pronged design — implementer ships BOTH (operator decides at OQ-paired triage which to actually run):
- **Forward-only path**: contract widened; future Path A labeler invocations emit the new keys; existing 34 exemplars remain on legacy shape. Default if operator does not opt to re-label.
- **Re-label-corpus operator-paired script** (CLI subcommand `swing diagnose relabel-corpus --silver-tier` OR fold into existing patterns_label_silver subcommand with `--corpus-all` flag): invokes Path A labeler against all 34 corpus exemplars + re-persists `labeler_evidence_json`. Operator-paired (slow; ~34 subagent invocations; operator may want to spot-check).

**Discriminating tests:**
- Plant a Path A silver-label invocation against a fresh exemplar with subagent emitting `rule_criteria` + assert it's persisted into `labeler_evidence_json['rule_criteria']`.
- Plant a malformed `rule_criteria` element (missing required `rule_name` key) + assert `SilverLabelResponse.__post_init__` raises typed `ValueError` (NOT generic `KeyError`).
- Plant a legacy exemplar with `rule_criteria` absent from `labeler_evidence_json` → assert `/patterns/exemplars` VM falls back to current "(no rule_criteria payload available)" placeholder (no regression).
- Plant a re-label of an existing legacy exemplar via Path A → assert `labeler_evidence_json` rewritten with `rule_criteria` key + assert VM emits `criterion_rows` for that exemplar.
- Pre-existing test of `geometric_evidence_narrative` persistence unchanged (backward-compat regression anchor).

**V2 dependencies banked:**
- Path A subagent re-label of ALL 34 corpus exemplars is operator-paired (out of brief auto-mode scope).
- Path C backfill script retained for future cohort-import scenarios (e.g., if T4.SB+ Item 1 fix lights up an A+ pipeline that accumulates new auto-labeled exemplars).

### §B.3 Item 3 — Market-weather chart volume-axis noise (Cosmetic)

**Operator framing (verbatim):** "the volume portion does not need axis values (0, 1, 1e8). They add no real value and are distracting and should be stripped."

**Investigation: NONE.** Direct fix.

**Design:**

Strip y-axis tick labels on volume subplot for any chart helper that does not already do so. Code reading at `swing/web/charts.py` shows:
- `render_watchlist_thumbnail_svg:217` ALREADY calls `ax_vol.set_yticks([])` (compact thumbnail; correctly stripped).
- `render_hyprec_detail_svg:234-274` does NOT strip (line 270 sets `ax_vol.set_ylabel("Volume")` but does NOT strip ticks).
- `render_market_weather_svg:332-366` does NOT strip (line 364 calls `ax_vol.set_xticks([])` but NOT y-axis).
- `render_position_detail_svg:282+` is single-axis (no volume subplot); not relevant.

**Fix:** add `ax_vol.set_yticks([])` to `render_market_weather_svg` (after line 364) AND to `render_hyprec_detail_svg` (after line 267 or co-located near volume bar rendering). Both should be ASCII-clean already; no mathtext metacharacter risk.

**Code surfaces touched:** `swing/web/charts.py` (2 one-line additions).

**Discriminating tests (per Codex R1 MINOR #1 closure — precise assertion):**
- Render market_weather SVG against a planted bars fixture; parse via matplotlib API BEFORE serialization OR introspect rendered SVG with explicit-string assertion: assert `ax_vol.get_yticklabels()` returns empty list (NO numeric tick labels like `0`, `1`, `1e8`). NOT a broad "no `<text>` elements in volume axis" assertion — `ax_vol.set_ylabel("Volume")` intentionally remains AS text in the volume subplot.
- Symmetric assertion for `render_hyprec_detail_svg`.
- Pre-existing thumbnail test unchanged (acts as already-stripped regression anchor).

**Visual verification (operator-witnessed gate):** S2 post-fix render of `/dashboard` showing the market-weather chart with no volume tick labels. Mathtext lesson applies (no string-equality substitute for visual gate).

### §B.4 Item 4 — Lightning glyph removal from watchlist row (Cosmetic/UX)

**Operator framing (verbatim):** "Let's completely remove the lightning icon from the watchlist. The thumbnails are much better and the lightning icon causes them to be offset."

**Investigation: NONE.** Direct fix.

**Design:**

Delete line 14 of `swing/web/templates/partials/watchlist_row.html.j2` (the `{% if price and w.entry_target and price.price >= w.entry_target * 0.99 %}⚡{% endif %}` block). The "1% from entry_target" signal is already surfaced in the `% to pivot` column (line 28-30: `((price.price - w.entry_target) / w.entry_target) * 100`) — no replacement glyph needed.

**Audit: `_thumb_bytes` template fragment at lines 9-16** does NOT depend on the lightning glyph's flexbox/inline-block layout; the `<span class="watchlist-thumbnail">` (line 16) is the only inline element in the `<td>` (line 13-18) after the glyph removal. Confirmed by template-reading.

**Code surfaces touched:** `swing/web/templates/partials/watchlist_row.html.j2` (1-line deletion).

**Discriminating tests:**
- Render watchlist row with a ticker within 1% of entry_target; assert "⚡" substring is ABSENT from response HTML.
- Render watchlist row with a ticker far from entry_target; behavior unchanged (was already no-glyph).
- Visual verification (operator-witnessed gate): S2 post-fix render of `/watchlist` + dashboard top-5 confirming layout consistency.

**Note:** the existing brief mentioned an OQ "should `% to pivot` column gain a color-coded visual indicator to compensate?" Default V1: NO. The column already shows the percentage; color-coding is a separate UX decision banked V2 if operator wants it (no signal currently that they do).

### §B.5 Item 5 — Chart scope too narrow + JIT-vs-flat-file architectural Q (Medium)

**Operator framing (verbatim, UX):** "UCTT in today's hyp-rec table lists 'Chart unavailable — ...' in lieu of a chart. This is incorrect, ALL hyp-recs should be charted. Additionally, ALL watchlist items should be charted."

**Operator framing (verbatim, Architecture-Q):** "Only concern is eventual archive constraints. Generation of charts for every watchlist/rec/open trade on every trading day will build up. Likely not an issue for modern hardware for a very, very long time but just worth a question. Additionally, minor concern about collisions if the pipeline is re-run multiple times in a day. How is that handled WRT to the raster charts? Charts dynamically created would not have this issue (simply use the most recent data in the cache)."

**Production state:**
- `swing/web/chart_scope.py:130-131` emits banner `"Chart unavailable — this ticker isn't in today's charting scope (A+ candidates, open positions, and tag-aware watchlist top-10)."` for any ticker outside `_resolve_via_chart_targets` scope.
- `_step_charts` at `swing/pipeline/runner.py:2280-2429` writes 4 surface caches: `watchlist_row` (top-10 tag-aware; pipeline_run_id non-NULL) + `hyprec_detail` (A+ only — gated at line 2371) + `position_detail` (open trades; pipeline_run_id IS NULL per v20 §3.2) + `market_weather` (cfg benchmark; pipeline_run_id non-NULL).
- chart_renders cache substrate landed at T2.SB6a (commit `54fb531`); `refresh_chart_render` + `get_cached_chart_svg` ready for JIT consumers.
- Re-run collision: today's pipeline-write-through DELETEs then INSERTs on `(ticker, surface, pipeline_run_id, pattern_class)` key per v20 partial-UNIQUE indexes.

**Investigation: NONE for architecture decision (orchestrator-recommendation REVISED per operator framing to JIT-primary + minimal pre-gen).** OQ-5.1 (retention policy) + OQ-5.2 (JIT latency budget) + OQ-5.4 (re-run collision semantics) + OQ-5.5 (banner removal) need operator-paired triage post-brainstorm.

**Design (JIT-primary + minimal pre-gen):**

**Pipeline-time pre-gen scope (reduced):**
- `market_weather` — always-visible dashboard top chart; pre-gen REMAINS (latency-critical).
- `position_detail` — accessed within seconds of dashboard load when open trades exist; pre-gen REMAINS.
- `watchlist_row` thumbnails — REDUCED from top-10 tag-aware to **dashboard top-5 visible-by-default** (the rows that render on initial dashboard load). The other 5+ rows shift to JIT cache-miss.
- `hyprec_detail` — REMOVED from pre-gen (was A+-gated at runner.py:2371 → 0 rows today). Shifts entirely to JIT cache-miss; first expand of any hyp-rec (A+ or sub-A+) triggers live render.

**JIT cache-miss live-render hook (architecture LOCK per Codex R1 M#2 + M#3 closure):**

NEW helper `swing/web/chart_jit.py:get_or_render_surface(*, conn, ohlcv_cache, surface, ticker, pipeline_run_id, pattern_class=None, **renderer_kwargs) -> bytes | None`:
1. Read cache via `get_cached_chart_svg(conn, surface=surface, ticker=ticker, pipeline_run_id=pipeline_run_id_or_NULL_per_surface, pattern_class=pattern_class)`.
2. On hit: return cached bytes.
3. On miss: fetch OHLCV via `ohlcv_cache.get_or_fetch(ticker=ticker, window_days=200)` (per existing `_step_charts._bars_or_none` precedent at `swing/pipeline/runner.py:2304`); on OHLCV failure return None.
4. Dispatch to appropriate renderer per `surface`: `watchlist_row` → `render_watchlist_thumbnail_svg`; `hyprec_detail` → `render_hyprec_detail_svg`; `position_detail` → `render_position_detail_svg`; `market_weather` → `render_market_weather_svg`. Renderer kwargs threaded per surface (e.g., position_detail needs trade + fills + current_stop — these come from the CALLER not the JIT helper).
5. Construct ChartRender dataclass (F6 construction-barrier defense applies — empty-bytes raises ValueError; helper catches + returns None + WARN-logs); on construction success, write-through via `refresh_chart_render(conn, chart_render)`; return bytes.
6. On render failure (matplotlib exception / OHLCV missing / ValueError at ChartRender construction): WARN-log + return None.

**Chart-scope LOCK (per Codex R1 M#2 closure):** `swing/web/chart_scope.py:resolve_chart_scope` REMAINS a pure availability-check function for the `/charts/<date>/<ticker>.png` PNG-on-disk path. It does NOT invoke JIT. The JIT invocation lives in the route handlers / VM builders that have the necessary dependency context (`conn`, `ohlcv_cache`, surface-specific render kwargs).

**Wiring (per Codex R1 M#3 closure — explicit dependency threading):**
- Watchlist row partial JIT integration (Item 5 ∩ Item 6 combined): `swing/web/routes/watchlist.py:watchlist_row` + `:watchlist_expand` route handlers gain access to `request.app.state.ohlcv_cache` (the existing `OhlcvCache` instance already on app.state per `swing/web/app.py` lifespan setup). Both routes invoke `get_or_render_surface(surface='watchlist_row', ticker=ticker.upper(), pipeline_run_id=binding.run_id, ...)`. Result populates `WatchlistRowVM.chart_svg_bytes` (or `vm.watchlist_chart_svg_bytes` mapping per Item 6 §B.6 design); template renders inline.
- Hyp-rec expand route JIT integration (Item 5 ∩ Item 7 broader audit): identify the route handler that renders the hyp-rec expanded detail view (currently no `chart_renders.hyprec_detail` consumer because A+ candidates are absent; verify route name at writing-plans phase). Thread `request.app.state.ohlcv_cache` through; invoke `get_or_render_surface(surface='hyprec_detail', ticker=ticker.upper(), pipeline_run_id=binding.run_id, ...)`.
- Existing chart-unavailable banner: when JIT helper returns None (renderer failure / OHLCV missing), surface a NEW banner reason `'render-failed'` or `'ohlcv-missing'` per Codex M#2 distinction (the existing `out-of-scope` reason becomes unreachable for these two surfaces once JIT wires in). Banner code path preserved per OQ-5.5 disposition.

**ohlcv_cache app-state availability check (LOCK):** `swing/web/app.py` lifespan setup already constructs `app.state.ohlcv_cache: OhlcvCache | None` for the existing pipeline + dashboard surfaces (per T1.SB0 LOCK at `swing/web/ohlcv_cache.py`). Verify at writing-plans phase via grep `app.state.ohlcv_cache` to confirm the helper is reachable from the routes. If NOT, plan §H must include "thread OhlcvCache to web app.state lifespan" as a prerequisite task.

**Re-run collision semantics (OQ-5.4 needs operator triage):**

Two design options surface in brainstorm:
- **Option A (orchestrator-default):** dashboard reader continues consuming the most-recent COMPLETE pipeline_run's snapshot (`latest_completed_pipeline_run`). If a fresh pipeline run lands mid-session, dashboard re-reads point to the new run. JIT cache-miss writes are anchored to the CURRENT-at-the-time-of-miss pipeline_run_id (matching the dashboard reader's anchor). Cleanest semantically; preserves existing chart_scope binding contract.
- **Option B (operator framing's literal reading "simply use the most recent data in the cache"):** dashboard reader consumes whatever chart_renders row is most-recent regardless of pipeline_run anchor. Simpler but introduces cross-run staleness drift (chart from pipeline_run_N shown alongside metrics from pipeline_run_(N+1)).

**Orchestrator recommendation: Option A.** The operator framing reads as a casual "no need to be clever" assertion, but the chart-vs-metrics consistency invariant (dashboard reader binds all surfaces to one pipeline_run anchor) is load-bearing. The brainstorm spec SURFACES this distinction explicitly — operator should triage in OQ-5.4.

**Cache retention policy (OQ-5.1 needs operator triage):**

Brainstorm surfaces 4 options:
- **R1**: Unbounded growth (today's behavior). Back-of-envelope: ~70 watchlist + 8 hyp-recs + 2 open positions + 1 market_weather ≈ 80 surface-rows/day × 252 trading days ≈ 20,160 rows/year × ~15 KB/SVG ≈ ~300 MB/year. Likely not an issue for modern hardware for years — but unbounded.
- **R2**: Retain N pipeline_runs (e.g., N=5; ≈ ~10 days of trading-day pipeline runs at 1/day). Old rows DELETE'd at `_step_charts` start. Simple TTL; no schema change.
- **R3**: Retain by age (e.g., > 60 days = DELETE). Simple TTL; no schema change.
- **R4**: Manual operator-triggered prune CLI (`swing diagnose prune-chart-cache --older-than DAYS`). Surface deferred until operator observes growth.

**Orchestrator recommendation: R4 + R1 default + reserve R2/R3 V2.** Operator's framing ("Likely not an issue for modern hardware for a very, very long time") argues for V1 deferred prune; CLI surface lets operator trigger when (if) they observe growth. R2/R3 are V2 if operator wants automation.

**JIT latency budget (OQ-5.2 needs operator triage):**

Matplotlib first-render is typically 200-500ms per chart (excluding OHLCV fetch) — this is an UNVERIFIED ESTIMATE based on general matplotlib timing (per Codex R1 MINOR #2). Operator's expand-and-view UX expects sub-second; the worst case is cold-OHLCV-cache + cold-Schwab-token + first-render = ESTIMATED ~1-2 seconds (also unverified — depends on OHLCV cache state + ticker count + yfinance/cache backoff behavior). **A measured-timing diagnostic ships as part of T-T4.SB.1 OR T-T4.SB.3** (subprocess-or-pytest harness that invokes the JIT helper against a representative test fixture + reports rendered-byte-count + render-time-ms) so the operator's OQ-5.2 triage decision is data-informed. Brainstorm proposes:
- **Synchronous JIT render — no timeout** (V1 default): expand handler blocks until render completes OR raises. On exception (renderer failure / OHLCV cache empty / etc.), surface a fallback banner ("Chart unavailable — render failed"). Worst-case operator wait under cold-everything path is ~1-2 seconds; acceptable for operator-paced workflow.
- **Synchronous JIT render — with wallclock timeout** (V1 alternative): wrap the render call in `concurrent.futures.ThreadPoolExecutor.submit + future.result(timeout=N)`; on timeout, return placeholder + 202 status; operator manually retries by re-expanding. ~30 LOC more than no-timeout; useful only if operator confirms wait sensitivity at OQ-5.2.
- **Async-render with HTMX placeholder swap** (V2 if operator observes UX regression): HTMX response with immediate "Chart loading..." + background-worker render + delayed swap via `hx-trigger` polling. Complex; defers V2.

**Chart-unavailable banner removal (OQ-5.5 needs operator triage):**

Once JIT path lights up, the `out-of-scope` banner becomes unreachable for `watchlist_row` + `hyprec_detail`. Three options:
- Delete the banner code path entirely (cleanest).
- Keep as fallback for genuine errors (e.g., OHLCV cache empty after JIT render attempt).
- Repurpose for explicit "render-error" reason states (`fetcher_failed`; `too_few_bars`).

**Orchestrator recommendation:** option (b) — keep as fallback. The genuine-error states preserve operator signal; banner copy text updated to reflect "render failure" not "out-of-scope" semantically. The literal `out-of-scope` reason becomes unreachable but the message dispatch table stays for the other reasons.

**Code surfaces touched:**
- NEW module `swing/web/chart_jit.py` (~80 LOC).
- `swing/web/chart_scope.py` — UPDATE `_resolve_via_chart_targets` to invoke JIT hook on miss; preserve heuristic fallback.
- `swing/web/routes/watchlist.py` + `swing/web/routes/dashboard.py` (or applicable) — wire JIT helper into watchlist + hyp-rec render paths.
- `swing/pipeline/runner.py:_step_charts` — REDUCE pre-gen scope per design (4 surfaces → 2 surfaces with watchlist trimmed to dashboard-top-5).
- Possibly NEW CLI `swing diagnose prune-chart-cache --older-than DAYS` (OQ-5.1 R4 disposition).

**Discriminating tests:**
- Plant a sub-A+ hyp-rec (UCTT today's pattern) + expand → assert chart_renders cache row populated after first expand; assert identical bytes on second expand (cache hit).
- Plant an OHLCV cache empty for a ticker + invoke JIT → assert WARN-log + None bytes + fallback banner emitted.
- Plant 2 concurrent pipeline_runs (run_N + run_N+1) + invoke JIT during run_N+1's window → assert JIT writes pipeline_run_id matching the dashboard reader's anchor (Option A semantic).
- Pre-gen scope reduction test: assert `_step_charts` writes ONLY market_weather + position_detail + dashboard-top-5 watchlist after the change (not top-10).
- Retention policy test (if R4 prune CLI shipped): plant 100 chart_renders rows of varied age + invoke prune CLI → assert older-than-DAYS rows DELETE'd.

**Architectural decisions:**
- **JIT-primary + minimal pre-gen** (per operator framing).
- **Cache key shape preserved** (per T2.SB6a semantic-contract gotcha): run-bound surfaces (`watchlist_row`, `hyprec_detail`, `market_weather`) write `pipeline_run_id` non-NULL; `position_detail` writes NULL. JIT writes honor the SAME contract.
- **F6 construction-barrier defense preserved** (per T2.SB6a F6 lesson): JIT helper writes through `ChartRender(...)` construction; empty-bytes raises at construction; cache row never DELETE'd-then-blanked.

**V2 dependencies banked (if not closed at OQ triage):**
- Async-render with HTMX placeholder swap (OQ-5.2 deferred).
- Automated retention policy R2/R3 (OQ-5.1 R4 default).
- Exemplar `chart_renders` surface — currently `swing/cli.py:patterns_exemplars_backfill_labeler_evidence` and `/patterns/exemplars` render exemplar charts; T2.SB6c V1 simplification row 4 ("exemplar cache-miss write-through skips when no completed pipeline run exists") may need re-examination once Item 5 architecture lands. Banked as Item-5-adjacent V2 follow-up.

### §B.6 Item 6 — Watchlist expand-then-collapse loses thumbnail (UX)

**Operator framing (verbatim):** "When expanding and then collapsing a dashboard watchlist item, the thumbnail disappears."

**Production state confirmed by code reading:**
- Watchlist row partial at `swing/web/templates/partials/watchlist_row.html.j2:9`: `{% set _thumb_bytes = vm.watchlist_chart_svg_bytes.get(w.ticker) if vm is defined and vm.watchlist_chart_svg_bytes else None %}`.
- Collapse route at `swing/web/routes/watchlist.py:28-54` (`@router.get("/watchlist/{ticker}/row")`) passes ONLY `w`, `price`, `tags`, `pattern_tag`, `current_pivot` to the template context. `vm` is NOT in the context.
- Result: `vm is defined` returns False → `_thumb_bytes` is None → thumbnail vanishes on collapse.

**Investigation: NONE.** Direct fix — code reading confirms root cause.

**Design (per Codex R1 M#7 closure — minimal partial-rewire chosen over VM extension):**

Two options weighed:

- **Option 6A (extend WatchlistRowVM + pass as `vm`)**: extend `WatchlistRowVM` with `watchlist_chart_svg_bytes: Mapping[str, bytes]` (singleton dict `{w.ticker: bytes}` matching the existing `WatchlistVM.watchlist_chart_svg_bytes: Mapping[str, bytes]` field at line 59); collapse route passes `{"vm": row_vm, ...}` (the `vm.watchlist_chart_svg_bytes.get(w.ticker)` template dereference resolves). Risk: the template `vm` dereference becomes silently context-dependent on TWO different VM shapes (WatchlistVM-from-page-render and WatchlistRowVM-from-collapse-route); future field drift could re-introduce the gap.
- **Option 6B (RECOMMENDED — partial rewire)**: change `swing/web/templates/partials/watchlist_row.html.j2:9` from `{% set _thumb_bytes = vm.watchlist_chart_svg_bytes.get(w.ticker) if vm is defined and vm.watchlist_chart_svg_bytes else None %}` to a direct `_thumb_bytes` template parameter looked up from a smaller, explicitly-named context variable (e.g., `chart_svg_bytes_for_row` passed by EVERY caller). Both the page-render path (in `watchlist.html.j2` / `dashboard.html.j2`) AND the collapse route MUST be updated to pass it.

**Orchestrator recommendation: Option 6B (partial rewire).** Codex R1 M#7 surfaced that Option 6A repeats the original drift mechanism — partials dereferencing `vm.foo` against contexts that might lack `vm`. Option 6B makes the per-row thumbnail bytes an EXPLICIT template-parameter input; the contract is uniform across page-render + collapse-route. Slightly more invasive (touches both callers) but structurally safer.

**Code surfaces touched (Option 6B):**
- `swing/web/templates/partials/watchlist_row.html.j2:9` — replace `vm.watchlist_chart_svg_bytes.get(w.ticker)` dereference with direct `_thumb_bytes` parameter; rename the Jinja `{% set %}` to `{% set _thumb_bytes = chart_svg_bytes_for_row if chart_svg_bytes_for_row is defined else None %}` for clarity.
- `swing/web/templates/watchlist.html.j2` (or wherever page-render includes the partial): update the `{% include "partials/watchlist_row.html.j2" with chart_svg_bytes_for_row=vm.watchlist_chart_svg_bytes.get(w.ticker) %}` pattern (or analogous).
- Dashboard top-5 watchlist render path: update the `{% include %}` call similarly.
- `swing/web/routes/watchlist.py:watchlist_row` collapse route: extend the template context dict with `chart_svg_bytes_for_row=<cache lookup for ticker>`. Cache lookup invokes the JIT helper from Item 5 (`get_or_render_surface(surface='watchlist_row', ticker=ticker.upper(), pipeline_run_id=..., conn=conn, ohlcv_cache=request.app.state.ohlcv_cache)`).
- No `WatchlistRowVM` extension needed under Option 6B (existing dataclass stays unchanged).

**Coupling with Item 5 (LOCK):** Item 6's collapse-route fix INVOKES the Item 5 JIT helper. T-T4.SB.5 MUST sequence after T-T4.SB.3 (Item 5 JIT helper landed first).

**Cumulative HTMX-OOB-swap gotcha applicability:** the CLAUDE.md gotcha "HTMX OOB-swap partials that hand-duplicate full-page markup drift silently" identifies the FAILURE FAMILY but NOT this exact mechanism. Here the partial is NOT hand-duplicated — it's the SAME `{% include %}` target, but with an INCOMPLETE context dict. Operationally same outcome (drift between full-page render and partial-swap render); banking refinement of the gotcha as "OOB-swap context dict must include vm" — applicable to all future include-based partials that dereference `vm.foo` fields.

**Discriminating tests:**
- Render full dashboard → snapshot watchlist row HTML (with thumbnail SVG inline). Issue HTMX expand request → snapshot expanded HTML. Issue HTMX collapse request → assert collapsed HTML CONTAINS the `<span class="watchlist-thumbnail">` element (NOT just absence of expansion).
- Plant a ticker with NULL `chart_svg_bytes` in cache + JIT helper returns None → collapse → assert NO thumbnail element + NO 500 error (graceful degradation).
- Plant a ticker with cached chart_svg_bytes (cache hit) + collapse → assert SAME thumbnail bytes as the full-page render (no live re-render path).
- Partial-rewire regression test: page-render template passes `chart_svg_bytes_for_row` AND collapse-route passes `chart_svg_bytes_for_row` → both paths emit IDENTICAL `<span class="watchlist-thumbnail">` element when cache populated.
- Pre-existing watchlist render tests unchanged.

**Operator-witnessed gate (S2):** real browser test of expand-collapse-expand sequence; thumbnail persists across all three.

**V2 dependencies banked:** none — this is a one-route fix.

### §B.7 Item 7 — Metrics wiring audit + hyp-progress=0 specific defect (HIGH)

**Operator framing (verbatim):** "The metrics need a thorough review to ensure they are properly hooked up. Specific example: the hypothesis progress card is reporting 0 for all hypothesis which is incorrect, several sub-A+ VCP not formed having been executed. two wins are running, several losses have been closed."

**Investigation: YES — TWO-PHASE.**

#### §B.7.1 Phase 1 — Specific defect diagnostic (`compute_hypothesis_progress_breakdown` / dashboard card)

**Production state confirmed by code reading:**

There are **TWO matching strategies** inconsistently applied across hypothesis-progress surfaces:

- **CLI path** at `swing/journal/stats.py:325 compute_hypothesis_progress_breakdown` uses `_label_matches_hypothesis` (prefix match, case-insensitive) — confirmed at `swing/recommendations/hypothesis.py:416-435`.
- **Dashboard path** at `swing/web/view_models/metrics/hypothesis_progress_card.py:404 build_hypothesis_progress_card_vm` → `_build_cohort_vm` (line 324) → `list_closed_trades_for_cohort` (`swing/metrics/cohort.py:84`) → `list_trades_for_cohort` (line 40) → SQL `WHERE hypothesis_label = ?` (line 67) with `canonical = canonicalize_hypothesis_label(hypothesis_label)` (line 59-62) — **EXACT-EQUALITY match** against the canonicalized hypothesis registry name.

`canonicalize_hypothesis_label` at `swing/trades/entry.py:184-209` is a Unicode-normalization helper (NFC normalize + drop Cf/Cc + collapse whitespace) — it does NOT strip the "(watch); failed: ..." suffix that `_descriptive_label` at `swing/recommendations/hypothesis.py:259` appends.

**Result:** operator's trade labels (verbatim from §B.7 diagnostic evidence: `"Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness"`) canonicalize to themselves; dashboard card query `WHERE hypothesis_label = 'Sub-A+ VCP-not-formed'` returns 0 rows. CLI path `_label_matches_hypothesis` would prefix-match correctly and return 4 (3 reviewed + 1 closed).

**Root cause: candidate (a) "string drift / lack of canonicalization at persistence"** PER operator-supplied root-cause hypothesis CONFIRMED in code. Specifically: the suffix-bearing labels persist via `_descriptive_label` builder; canonicalization-at-persistence helper does NOT strip the suffix; dashboard card uses exact-equality match.

**Diagnostic design (V1: confirm root-cause-(a); validate other surfaces):**

NEW instrument lives in CLI under `swing/cli.py:diagnose_metrics_wiring` (or fold into Item 1's `swing diagnose` subcommand-group). The diagnostic:
- Lists every metric surface in `swing/metrics/` + `swing/web/view_models/metrics/` + `swing/journal/stats.py:render_hypothesis_progress` + dashboard cards.
- For each surface that performs a `hypothesis_label` lookup OR an analogous canonical-grouping-key lookup, identify:
  - Match strategy (exact equality / prefix-match / canonical-prefix-strip / SQL LIKE / etc.).
  - Persistence-time canonicalization helper invoked (if any).
  - Disposition (LIVE / V1 STUB / V1 PLACEHOLDER).
- Output: deterministic markdown table at `exports/diagnostics/metrics-wiring-audit-<ISO>.md`.

**Diagnostic output expected to surface 1 confirmed defect (hypothesis-progress card exact-vs-prefix mismatch) + possibly more:** the operator's S7 gate observation ("reached_1R/hit_stop 'no trade pairing or n<5'") is the T2.SB6c V1 simplification row 1 (outcome distribution uses `realized_R_if_plan_followed` surrogate) + the absence of trade backlinks pre-v21 — likely correctly suppressed but worth audit-table presence. Queue empty is the T2.SB6c V1 simplification row 4 (exemplar cache-miss skips when no pipeline_run).

**Fix design (post-diagnostic):**

**Canonical resolution: canonicalize-at-persistence-boundary.** Strip the `(watch); failed: ...` suffix at the entry-form POST handler when persisting `trades.hypothesis_label`. Two-tier canonicalization:

- **Tier 1** (existing): Unicode normalize + whitespace collapse via `canonicalize_hypothesis_label`. Preserved verbatim.
- **Tier 2** (NEW): hypothesis-prefix canonicalization — given a free-text label + the registry of known hypothesis names, identify the longest registered hypothesis-name prefix + persist `hypothesis_label = <canonical_hypothesis_name>` PLUS persist the suffix in a NEW companion column (NULL if no suffix).

**Schema decision (NEEDS OPERATOR TRIAGE OQ-7.3):**

Two options surface in brainstorm:
- **Option 7A (NO schema change)**: tier-2 canonicalization strips the suffix entirely at persistence; the per-trade "failed: ..." detail is LOST. Simplest; loses provenance.
- **Option 7B (NEW NULLable column `trades.hypothesis_label_suffix`)**: tier-2 canonicalization persists canonical name to `hypothesis_label` AND raw suffix to `hypothesis_label_suffix`. Preserves provenance; schema bump to v22. Read-path consumers join + display the suffix in detail views.
- **Option 7C (canonicalize-at-READ-time with DELIMITER-AWARE matching)**: dashboard query rewritten to match canonical name PLUS recognized suffix delimiters. Persistence unchanged. NO schema change. Operator's per-trade suffix preserved.

**Orchestrator recommendation: Option 7C** (NO schema change; delimiter-aware prefix-match consistent with the CLI path). Rationale:
- **Avoids schema bump** (T4.SB's expected schema-UNCHANGED posture preserved).
- **Preserves operator's per-trade suffix** (the suffix encodes which criteria failed for THIS trade — useful for retrospective review).
- **Matches CLI's existing semantic** (`_label_matches_hypothesis` already does this).
- **Closes the wiring inconsistency** (CLI + dashboard converge on one match strategy).

**Delimiter-aware matching contract (per Codex R1 M#4 closure):** the existing `_label_matches_hypothesis` uses bare `startswith` (case-insensitive) — this is TOO BROAD because labels like `Sub-A+ VCP-not-formedness ...` would prefix-match `Sub-A+ VCP-not-formed`. Both the CLI helper AND the new SQL helper MUST use **delimiter-aware** matching: a label MATCHES a hypothesis name when (and only when) one of these holds:

1. `label == name` (exact equality after case-fold).
2. `label.lower().startswith(name.lower() + " ")` (space delimiter — matches `_descriptive_label` output: `"<hypothesis_name> (<bucket>); failed: ..."`).
3. `label.lower().startswith(name.lower() + ";")` (semicolon delimiter — defensive against future label variants).

Rejected: bare `startswith`; bare SQL `LIKE 'name%'` (matches `name`-prefixed extensions of name); naive `LIKE 'name (%'` only (misses exact equality + future variant suffixes).

**SQL implementation** (for `swing/metrics/cohort.py:list_trades_for_cohort` rewrite): replace `WHERE hypothesis_label = ?` with `WHERE LOWER(hypothesis_label) = LOWER(?) OR LOWER(hypothesis_label) LIKE LOWER(?) || ' %' ESCAPE '\' OR LOWER(hypothesis_label) LIKE LOWER(?) || ';%' ESCAPE '\'` (3 parameters; cohort_name passed thrice). **`ESCAPE '\'` clause + escape SQL wildcards `%`/`_` in cohort_name before binding** — hypothesis names today are clean but a future registry entry containing `%` or `_` would silently broaden the match without escaping. A `_sql_escape_wildcard(name: str) -> str` helper replaces `\` → `\\`, `%` → `\%`, `_` → `\_` before binding.

**Python helper refactor (LOCK):** to avoid two-mirror divergence (existing CLI helper at `swing/recommendations/hypothesis.py:416-435` vs new SQL semantic), introduce a SHARED canonicalization at `swing/recommendations/hypothesis.py` (or new `swing/metrics/label_match.py`):
- `_label_matches_hypothesis(label, name)` Python: rewrite to use the 3-rule delimiter-aware match (the existing `startswith` widens to the 3-tuple).
- `_label_matches_hypothesis_sql(name) -> tuple[str, list[object]]` returns the `WHERE`-clause-fragment + binding params (with wildcard-escape) for the SQL surface.
- Discriminating test asserts Python helper + SQL helper produce IDENTICAL match sets on a fixed corpus of test labels.

Cumulative gotcha applies: "Grouping-key fields need canonicalization-at-persistence-boundary, not just display safety" (orchestrator-context Tranche B-ops). But the existing canonicalization handles Unicode/whitespace; the hypothesis-prefix dimension is a NEW dimension that's better handled at READ-time given the operator's explicit per-trade-suffix value. The gotcha applies UPDIRECTIONAL — DO canonicalize at persistence for non-business-meaning artifacts (whitespace; Unicode); do NOT canonicalize at persistence for business-meaningful suffixes that the operator wants persisted.

#### §B.7.2 Phase 2 — Broader metrics-wiring audit

Per operator framing: "The metrics need a thorough review to ensure they are properly hooked up."

**Audit scope:**

Enumerate every metric surface:
- `swing/metrics/*.py` modules (process; cohort; discrepancies; policy; honesty; rolling_window; etc. — Phase 10 dashboard surfaces).
- `swing/web/view_models/metrics/*.py` (per-tile VM builders).
- `swing/web/templates/metrics/*.html.j2` (per-tile templates).
- `swing/journal/stats.py` render functions (CLI hyp-rec progress).
- Dashboard cards in `swing/web/view_models/dashboard.py` + templates in `swing/web/templates/dashboard*.html.j2`.

**Per-surface checklist (4 items per surface; codified per the T2.SB6c V1-simplification banking pattern):**
- **(i) Data source query against current operator DB row distribution** — does the surface query the right table(s) with the right WHERE clauses?
- **(ii) State-filter scope vs operator expectation** — does the filter (`state IN (...)`) match operator's mental model of "in-flight" vs "closed" trades?
- **(iii) Join semantics vs persisted FK reality** — are joins on the right keys; do they survive v21 trade-backlinks (`trades.candidate_id` + `trades.pattern_evaluation_id`) populated vs NULL?
- **(iv) Discriminating round-trip test** — plant N rows of the canonical shape; render; assert the metric reflects N (defends against the false-zero failure family).

**Audit output:**

Deterministic markdown table at `exports/diagnostics/metrics-wiring-audit-<ISO>.md` (the same diagnostic emits both Phase 1 + Phase 2 audit content). One row per surface; columns: surface_name, file_path, match_strategy, state_filter, join_keys, current_operator_DB_count, T4_SB_audit_disposition (LIVE / V1 STUB / V1 PLACEHOLDER / WIRING DEFECT / FALSE-ZERO RISK).

**Fix scope (driven by audit):**

T4.SB MAY close audit-identified WIRING DEFECT entries inline (small fixes; like the hypothesis-progress card's exact-vs-prefix mismatch). FALSE-ZERO RISK entries that originate in V1 simplifications (T2.SB6c return report §4.1) MAY be closed if marginal cost is low; otherwise banked V2 with V2 dependency cited.

**Code surfaces touched (estimated):**
- `swing/metrics/cohort.py:list_trades_for_cohort` (or callsite) — switch from exact-equality to prefix-match (Option 7C); OR introduce a `_label_matches_hypothesis_sql` helper that's invoked by both paths.
- `swing/web/view_models/metrics/hypothesis_progress_card.py:_build_cohort_vm` — verify match strategy converges.
- Per audit findings: any other wiring defects identified.
- NEW module `swing/diagnostics/metrics_wiring_audit.py` (~120 LOC).
- NEW CLI subcommand `swing diagnose metrics-wiring` (sibling of Item 1's `swing diagnose aplus-blockers`).

**Discriminating tests:**
- Plant N trades with `hypothesis_label='Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness'` → render dashboard hyp-progress card → assert `n_closed` reflects N (not 0).
- Plant a trade with `hypothesis_label = exact canonical name (no suffix)` → assert still matches (prefix-match preserves backward compat).
- Plant a trade with `hypothesis_label = 'Random label not matching any registered hypothesis'` → assert NO false-positive across all 4 registered hypotheses.
- Per audit-identified additional defects: per-defect discriminating round-trip test.

**Architectural decisions:**
- **Option 7C (READ-time prefix-match canonicalization)** UNLESS operator triage OQ-7.3 prefers Option 7A or 7B.
- **Broader-audit scope = all metric surfaces** (not just hyp-progress).
- **Diagnostic-then-fix sequencing** (OQ-7.1): diagnostic ships FIRST as part of T-T4.SB.1; fixes derive from diagnostic output in T-T4.SB.2 (per executing-plans phase decision).
- **Audit table is a permanent artifact** (committed to repo; cycle-checklist references it for future drift-detection).

**V2 dependencies banked (if not closed at OQ triage):**
- Trade-backlink-aware metric tiles (require v21 backlinks consumed throughout audit-identified surfaces; partial coverage already in T2.SB6b/c).
- Outcome distribution V2-OHLCV-aware variant (T2.SB6c row 1 banking preserved).
- Per-defect V2 banking with V2 dependency cited per audit row.

---

## §C Cross-item couplings

### §C.1 Item 1 ↔ Item 7 — shared "false-zero on closed-loop surface" failure-mode family

Item 1 reports 0 A+ candidates (market-output OR calibration miss). Item 7 reports 0 hypothesis-progress across 8 trades (surface-vs-data wiring miss). Both surface false-zeros that violate operator's "ships are designed to go to sea" expectation.

**Coupling:** Item 1 diagnostic OUTPUT may inform Item 7 broader audit — e.g., other metric surfaces may have analogous filter-too-tight issues. The Item 7 broader audit specifically enumerates 4 per-surface checklist items (i-iv); Item 1 diagnostic's per-criterion blocking distribution may surface candidate analogues at the criterion-level.

**Dispatch implication:** investigation sequencing places Item 1 + Item 7 specific-defect diagnostics in T-T4.SB.1 (one task; complementary work; both feed downstream tasks).

### §C.2 Item 1 ↔ Item 2 — coupled-via-detector-pipeline

Item 2's Path A labeler subagent contract widening only matters if fresh exemplars accumulate. While 0 A+ persists (Item 1), fresh exemplars do NOT accumulate organically. **Outcome dependency:**
- If Item 1 diagnostic confirms market-output (no calibration miss), Item 2 fix unblocks future cycles when market regime shifts back to producing A+.
- If Item 1 diagnostic confirms calibration miss (proposes threshold loosening), Item 2 fix must land BEFORE the threshold-loosening lands in cfg-policy — otherwise newly-emerging exemplars persist with legacy shape.

**Dispatch implication:** Item 2 (T-T4.SB.4) depends on Item 1 outcome; can run concurrent with Items 3/4/6 cosmetic/UX, but Item 1 diagnostic (T-T4.SB.1) must complete before Item 2 ships.

### §C.3 Item 1 ↔ research branch — first-method-record selection dependency

Per `research/phase-0-tasks.md` "Later (deferred)" — Item 1 diagnostic OUTPUT feeds research-branch first-method-record selection. Spec acknowledges; T4.SB does NOT pre-commit to a research outcome.

**Dispatch implication:** Item 1 diagnostic OUTPUT is a binding artifact (committed; operator-readable); research-branch authoring is separately governed.

### §C.4 Item 5 ↔ Item 6 — shared HTMX-driven dashboard watchlist surface

Item 5 (chart scope architecture; JIT cache-miss) constrains the partial-template structure that Item 6 (collapse-handler) must round-trip. Specifically: Item 5's pre-gen scope reduction (watchlist top-10 → top-5) reduces the number of rows with pre-populated thumbnails; Item 6's collapse-handler fix (extend WatchlistRowVM with chart_svg_bytes mapping) must work for BOTH pre-gen'd thumbnails AND JIT-rendered thumbnails.

**Dispatch implication:** Item 5 (T-T4.SB.3) + Item 6 (T-T4.SB.5) can run concurrently, but the Item 5 cache-miss hook + Item 6 collapse-handler fix MUST share the same "chart_svg_bytes resolves via JIT helper" semantic. Recommend: Item 6 collapse-handler invokes the SAME JIT helper that Item 5 introduces. Encode this dependency in the writing-plans phase.

### §C.5 Item 3 ↔ Items 4, 6 — shared chart-rendering surface area

Items 3 (volume-axis), 4 (lightning glyph), and 6 (watchlist collapse) all touch the watchlist-row + dashboard top-5 surface. Item 3 specifically touches `swing/web/charts.py` render helpers; Items 4+6 touch `swing/web/templates/partials/watchlist_row.html.j2` + `swing/web/routes/watchlist.py` + VM helpers.

**Dispatch implication:** Items 3+4+6 bundle naturally into T-T4.SB.5 (cosmetic/UX); minimal diff size; can be one Codex round.

---

## §D Investigation outputs format

### §D.1 Item 1 diagnostic output

**File:** `exports/diagnostics/aplus-blockers-<ISO>.md` + `exports/diagnostics/aplus-blockers-<ISO>.csv` (paired).

**Markdown layout** (excerpt; full schema):
```
# A+ Blockers Diagnostic

**Generated:** <ISO timestamp>
**Eval-runs window:** last N=20 runs (range <run_id_start>..<run_id_end>)
**Total candidates examined:** <N>
**A+ count in window:** <N>
**Watch count in window:** <N>
**Skip count in window:** <N>

## Per-criterion blocking distribution

| Criterion | Failed count | Failed % | Mean margin | Median margin | P90 margin | Sample tickers |
|---|---|---|---|---|---|---|
| trend_template_tt2_close_above_ma200 | 23 | 12% | 4.2pp | 3.8pp | 8.1pp | AAPL (8.1pp), MSFT (6.3pp), TSLA (5.4pp) |
| vcp_contraction_count | 47 | 24% | 1.2 contractions | 1 | 2 | <...> |
| ... | ... | ... | ... | ... | ... | ... |

## NA-by-thin-data rows

| Criterion | NA count | Reason distribution |
|---|---|---|
| ... | ... | ... |

## Notes
<free-text observations>
```

### §D.2 Item 7 metrics-wiring-audit output

**File:** `exports/diagnostics/metrics-wiring-audit-<ISO>.md`.

**Markdown layout:**
```
# Metrics Wiring Audit

**Generated:** <ISO timestamp>
**Surfaces audited:** N

## Per-surface table

| Surface | File:line | Match strategy | State filter | Join keys | Operator DB count | Audit disposition |
|---|---|---|---|---|---|---|
| Dashboard hyp-progress card | swing/web/view_models/metrics/hypothesis_progress_card.py:404 | exact-equality (BUG) | state IN ('closed','reviewed') | hypothesis_label = ? | 0 (suffix mismatch) | WIRING DEFECT — Option 7C fix in T-T4.SB.2 |
| CLI compute_hypothesis_progress_breakdown | swing/journal/stats.py:325 | prefix-match | state IN ('closed','reviewed') | _label_matches_hypothesis | 4 | LIVE |
| ... | ... | ... | ... | ... | ... | ... |

## Wiring-defect findings (per-defect detail)
<one section per WIRING DEFECT entry; reproduction recipe + fix path>

## False-zero risk findings (per-row detail)
<one section per FALSE-ZERO RISK entry; root cause + V2 dependency citation>
```

### §D.3 Output retention + cycle-checklist integration

Both outputs are committed to `exports/diagnostics/` (NOT to `docs/` — they're operational artifacts, not design docs). The cycle-checklist gets a NEW entry: "re-run `swing diagnose aplus-blockers` quarterly OR after major detector-criteria changes; archive outputs to `exports/diagnostics/archive/` as part of pre-merge housekeeping." Banked for cycle-checklist update at T-T4.SB.6 closer task.

---

## §E Cross-bundle pin

### §E.1 Does T4.SB introduce a NEW pin?

T4.SB introduces architecture changes (JIT cache-miss; metrics-wiring fixes) that COULD warrant a cross-bundle pin row 13. Two candidate pins surface:

**Candidate pin row 13a — chart_renders retention policy invariant:**
- Pin asserts: if R4 prune CLI ships, `swing diagnose prune-chart-cache --older-than 0` is a no-op for `position_detail` (NULL pipeline_run_id; semantically run-agnostic so age is from `rendered_at`). Useful only if R4 ships.
- **Recommendation: DO NOT plant** (R4 disposition is operator-triage-deferred; if R4 banks V2, pin doesn't need to land here).

**Candidate pin row 13b — hypothesis-label match-strategy invariant:**
- Pin asserts: at all canonical metric surfaces (`swing/metrics/cohort.py:list_trades_for_cohort`; `swing/web/view_models/metrics/hypothesis_progress_card.py:_build_cohort_vm`; `swing/journal/stats.py:compute_hypothesis_progress_breakdown`), a trade with `hypothesis_label = 'Sub-A+ VCP-not-formed (watch); failed: proximity_20ma'` matches the hypothesis named `'Sub-A+ VCP-not-formed'` (and does NOT match `'A+ baseline'`).
- Parametrized over the 3+ surfaces.
- **Recommendation: PLANT as row 13** at T-T4.SB.2 (Item 7 broader audit fix); promote GREEN at T-T4.SB.6 closer. Mirrors T2.SB6c row 12 (per-discipline parametrize).

### §E.2 Existing pins disposition

**Row 12** (T2.SB6c v21 trade backlinks atomic) — promoted GREEN at T-A.6c.5; remains GREEN through T4.SB (no schema regression risk).

**Existing pre-Phase-13 pins** (per Phase 13 main plan §H.3 / equivalent) — preserved verbatim; T4.SB does not touch their substrates.

### §E.3 Pin file location + naming

NEW pin file: `tests/metrics/test_phase13_t4_sb_cross_bundle_pin_row_13.py` (parametrized over the 3 surfaces). Pattern mirrors `tests/data/test_phase13_t2_sb6c_cross_bundle_pin_row_12.py` (T2.SB6c precedent).

Phase 13 main plan §H.3 row 13 to be appended at T-T4.SB.6 closer: `test_phase13_t4_sb_hypothesis_label_match_strategy_invariant`.

---

## §F Test scope projection

### §F.1 Baseline + projected delta

Baseline: 5670 fast tests at main HEAD `e75f743` (post T2.SB6c housekeeping). Projected T4.SB delta (per-task budget):

| Task | Fast tests | Slow tests | Fast E2E | Cumulative |
|---|---|---|---|---|
| T-T4.SB.1 (Item 1 + Item 7 specific-defect diagnostics) | +20-30 | 0 | 0 | ~5690-5700 |
| T-T4.SB.2 (Item 7 broader audit + canonical fix) | +15-25 | 0 | 0 | ~5705-5725 |
| T-T4.SB.3 (Item 5 architecture: JIT + pre-gen reduction) | +25-40 | 0 | 0 | ~5730-5765 |
| T-T4.SB.4 (Item 2 labeler contract widening) | +10-15 | 0 | 0 | ~5740-5780 |
| T-T4.SB.5 (Items 3+4+6 cosmetic/UX bundle) | +8-12 | 0 | 0 | ~5748-5792 |
| T-T4.SB.6 (closer + cross-bundle pin promotion + E2E) | +1-3 | 0 | +1 | ~5750-5795 + 1 E2E |

**Projected baseline at T4.SB SHIPPED: ~5750-5795 fast (+80-125 net) + 1 fast E2E.** Below T2.SB6c +111 by a margin; T4.SB is mostly investigation + cosmetic + small-architecture (no large refactor).

### §F.2 Slow-test discipline

Slow tests UNCHANGED. ZERO new Schwab API calls (L2 LOCK preserved); no slow yfinance E2E added. The 1 new fast E2E at T-T4.SB.6 closer mirrors T2.SB6c precedent.

### §F.3 Ruff discipline

Ruff baseline = 0 E501 violations. T4.SB preserves; per-task verification at writing-plans.

### §F.4 Test marker convention

All new T4.SB fast tests under `tests/diagnostics/` (NEW directory for Item 1 + Item 7 diagnostic modules), `tests/web/routes/` (existing; Item 6 collapse-handler + Item 5 JIT route tests), `tests/web/templates/` (existing; Item 3 + 4 template verification), `tests/metrics/` (existing; cross-bundle pin row 13). NO marker drift.

---

## §G Sub-bundle decomposition

### §G.1 Task list (BINDING; writing-plans phase refines per-task acceptance criteria)

#### §G.1.1 T-T4.SB.1 — Item 1 + Item 7 specific-defect diagnostics (combined investigation task)

**Scope:**
- NEW module `swing/diagnostics/aplus_blockers.py` (~150 LOC).
- NEW module `swing/diagnostics/metrics_wiring_audit.py` (~120 LOC).
- NEW CLI subcommand group `swing diagnose` (Click subcommand-group registration; sibling of `swing config`, `swing schwab`, etc.).
- NEW subcommands `swing diagnose aplus-blockers --eval-runs N --output PATH` + `swing diagnose metrics-wiring --output PATH`.
- Read-only against `candidates`, `evaluation_runs`, `trades`, `pattern_evaluations`, hypothesis registry. ZERO writes.
- ASCII-only stdout (cp1252 safety).
- Output writes to `exports/diagnostics/` (NEW directory; create on first run).

**Acceptance criteria:**
- `swing diagnose aplus-blockers --eval-runs 20 --output exports/diagnostics/aplus-blockers-test.md` produces a deterministic markdown report + CSV sidecar.
- `swing diagnose metrics-wiring --output exports/diagnostics/metrics-wiring-audit-test.md` produces a per-surface audit table.
- All discriminating tests at §B.1 + §B.7.1 GREEN.
- Both subcommands surface `--help` correctly; ASCII-only output verified via subprocess-stdout-capture test.

**Commit message templates:**
- `feat(diagnostics): aplus-blockers diagnostic subcommand (Item 1; T-T4.SB.1)`
- `feat(diagnostics): metrics-wiring-audit diagnostic subcommand (Item 7 Phase 1; T-T4.SB.1)`

**Test budget:** +20-30 fast tests.

#### §G.1.2 T-T4.SB.2 — Item 7 broader audit + canonical wiring fix

**Scope:**
- Consume output of T-T4.SB.1 `swing diagnose metrics-wiring` (audit table).
- Per WIRING DEFECT entry, fix inline.
- Specifically: hypothesis-progress card exact-vs-prefix mismatch (Option 7C READ-time prefix-match in `swing/metrics/cohort.py:list_trades_for_cohort`).
- Per FALSE-ZERO RISK entry, bank V2 with citation OR fix inline if marginal cost low.
- Cross-bundle pin row 13 PLANT (parametrized over 3+ surfaces).

**Acceptance criteria:**
- Dashboard hyp-progress card shows non-zero `n_closed` for `Sub-A+ VCP-not-formed` cohort with operator's 4 closed trades (assertable via integration test).
- CLI `compute_hypothesis_progress_breakdown` behavior unchanged.
- Cross-bundle pin row 13 PLANTED at `tests/metrics/test_phase13_t4_sb_cross_bundle_pin_row_13.py` (SKIPped pre-fix; GREEN at T-T4.SB.6 promotion).
- All per-defect discriminating tests GREEN.

**Commit message templates:**
- `fix(metrics): hypothesis_label prefix-match canonical wiring (Option 7C; Item 7; T-T4.SB.2)`
- `test(metrics): cross-bundle pin row 13 — hypothesis_label match-strategy invariant (T-T4.SB.2)`
- `chore(diagnostics): metrics-wiring audit V2-bank notes (T-T4.SB.2)` (if FALSE-ZERO RISK V2-banking needs docs)

**Test budget:** +15-25 fast tests.

#### §G.1.3 T-T4.SB.3 — Item 5 architecture (JIT cache-miss + pre-gen scope reduction)

**Scope:**
- NEW module `swing/web/chart_jit.py` (~80 LOC).
- `swing/web/chart_scope.py` UPDATE: `_resolve_via_chart_targets` invokes JIT hook on `out-of-scope` for `watchlist_row` + `hyprec_detail`.
- `swing/web/routes/watchlist.py` + `swing/web/routes/dashboard.py` (or applicable) wire JIT helper into render paths.
- `swing/pipeline/runner.py:_step_charts` REDUCE pre-gen scope: market_weather + position_detail PRESERVED; watchlist_row REDUCED top-10 → dashboard-top-5; hyprec_detail REMOVED.
- F6 construction-barrier defense preserved.
- Cache key shape preserved (run-bound non-NULL pipeline_run_id; position_detail NULL).
- (Conditional on OQ-5.1 R4) NEW CLI subcommand `swing diagnose prune-chart-cache --older-than DAYS`.

**Acceptance criteria:**
- Sub-A+ hyp-rec expand triggers live render + cache write-through (cache populated post-expand).
- Second expand of same ticker = cache hit (zero re-render).
- Pre-gen scope reduction asserted: `_step_charts` no longer writes `hyprec_detail` for A+; writes only dashboard-top-5 watchlist thumbnails.
- Re-run collision Option A semantic (JIT writes pipeline_run_id matching dashboard reader anchor) asserted via discriminating test.
- All per-design discriminating tests at §B.5 GREEN.

**Commit message templates:**
- `feat(web): JIT cache-miss chart-render hook + chart_scope wiring (Item 5; T-T4.SB.3)`
- `refactor(pipeline): _step_charts pre-gen scope reduction (Item 5; T-T4.SB.3)`
- (Conditional) `feat(diagnostics): prune-chart-cache subcommand (Item 5 R4; T-T4.SB.3)`

**Test budget:** +25-40 fast tests.

#### §G.1.4 T-T4.SB.4 — Item 2 labeler subagent contract widening

**Scope:**
- Subagent prompt update at `.claude/agents/pattern-labeler.md`.
- `_SilverLabelResponse` dataclass extension (NEW `rule_criteria` + `narrative` fields with `__post_init__` validation).
- `swing/cli.py:patterns_label_silver` + `_fire_claude_silver_label` parse + validate new keys.
- `labeler_evidence_json` envelope shape extension (JSON BLOB; no schema change).
- `/patterns/exemplars` template surfaces new keys; preserves legacy-row fallback.
- (Conditional on OQ-2.2) Re-label corpus operator-paired CLI flag/subcommand.

**Acceptance criteria:**
- Fresh Path A silver-label invocation emits + persists new keys.
- Malformed input raises typed exception (NOT generic KeyError; per `Literal[...]` runtime-enforcement gotcha).
- Legacy 34 corpus exemplars render with new template (LEGACY fallback "no rule_criteria; no narrative" preserved).
- All per-design discriminating tests at §B.2 GREEN.

**Commit message templates:**
- `feat(patterns): labeler subagent contract widening — rule_criteria + narrative (Item 2; T-T4.SB.4)`
- `feat(web): /patterns/exemplars template surfaces new labeler keys (Item 2; T-T4.SB.4)`
- (Conditional) `feat(cli): patterns-label-silver --corpus-all relabel flag (Item 2 V1; T-T4.SB.4)`

**Test budget:** +10-15 fast tests.

#### §G.1.5 T-T4.SB.5 — Items 3+4+6 cosmetic/UX bundle

**Scope:**
- Item 3: add `ax_vol.set_yticks([])` to `render_market_weather_svg` + `render_hyprec_detail_svg`.
- Item 4: delete line 14 of `swing/web/templates/partials/watchlist_row.html.j2`.
- Item 6: extend `WatchlistRowVM` with `chart_svg_bytes: bytes | None` (or `watchlist_chart_svg_bytes: Mapping[str, bytes]`); update `swing/web/routes/watchlist.py:watchlist_row` to pass extended VM via `vm` context key.
- Items 3+4+6 share template / partial / VM substrate; bundle as single sub-bundle with 3 commits OR 1 commit per item (writing-plans phase decides commit-granularity per per-task TDD discipline).

**Acceptance criteria:**
- Volume y-tick labels ABSENT from market_weather + hyprec_detail SVG outputs (parseable assertion).
- "⚡" glyph ABSENT from watchlist row HTML responses.
- Expand-collapse-expand sequence preserves thumbnail across all three states (DOM-level snapshot test; operator-witnessed gate confirms browser behavior).
- All per-design discriminating tests at §B.3 + §B.4 + §B.6 GREEN.

**Commit message templates:**
- `fix(web): strip volume y-tick labels on market_weather + hyprec_detail charts (Item 3; T-T4.SB.5)`
- `fix(web): remove lightning glyph from watchlist row (Item 4; T-T4.SB.5)`
- `fix(web): watchlist row collapse preserves thumbnail (Item 6; T-T4.SB.5)`

**Test budget:** +8-12 fast tests.

#### §G.1.6 T-T4.SB.6 — Closer

**Scope:**
- 1 NEW fast E2E covering operator-pre-witnessed gate flow (e.g., `tests/integration/test_phase13_t4_sb_closer_e2e.py` — pipeline run → dashboard render → hyp-rec expand → JIT chart hit → watchlist collapse preserves thumbnail).
- Cross-bundle pin row 13 PROMOTION (un-SKIP per §E recommendation).
- Phase 13 main plan §H.3 row 13 appendage.
- CLAUDE.md current-state line update: Phase 13 sub-bundle ship count 11 → **12 (FULLY CLOSED)**.
- `docs/orchestrator-context.md` "Currently in-flight work" update: T4.SB SHIPPED.
- Cycle-checklist update: quarterly `swing diagnose aplus-blockers` + `swing diagnose metrics-wiring` rerun reminders.
- Ruff sweep (0 E501).

**Acceptance criteria:**
- Fast suite GREEN (~5750-5795 fast tests).
- New E2E GREEN.
- Cross-bundle pin row 13 GREEN (un-SKIPped).
- Ruff clean.
- Phase 13 sub-bundle ship count = 12 of 12 announced via CLAUDE.md / orchestrator-context updates.

**Commit message templates:**
- `test(phase13): T4.SB closer + cross-bundle pin row 13 promotion + closer E2E (T-T4.SB.6)`
- `docs(phase13): T4.SB SHIPPED — Phase 13 FULLY CLOSED (12 of 12 sub-bundles) (T-T4.SB.6)`
- `docs(cycle-checklist): quarterly diagnostic re-runs scheduled (T-T4.SB.6)`

**Test budget:** +1-3 fast tests + 1 fast E2E.

### §G.2 Concurrent dispatch potential

- **T-T4.SB.1** runs FIRST (diagnostics inform downstream).
- **T-T4.SB.2** depends on T-T4.SB.1 audit output → SEQUENTIAL.
- **T-T4.SB.3** is independent of T-T4.SB.2 → CONCURRENT possible (but the Item 6 collapse-handler in T-T4.SB.5 depends on T-T4.SB.3's JIT helper; T-T4.SB.5 should land AFTER T-T4.SB.3).
- **T-T4.SB.4** is independent of all others → CONCURRENT possible.
- **T-T4.SB.5** depends on T-T4.SB.3 JIT helper → SEQUENTIAL after T-T4.SB.3.
- **T-T4.SB.6** depends on all others → SEQUENTIAL last.

**Recommended dispatch sequence (sequential; conservative):** T-T4.SB.1 → T-T4.SB.2 → T-T4.SB.3 → T-T4.SB.4 (or concurrent) → T-T4.SB.5 → T-T4.SB.6.

**Optionally concurrent:** T-T4.SB.4 can fire concurrent with T-T4.SB.2 or T-T4.SB.3 (writing-plans phase decides per subagent-driven-development capacity).

**Verification ordering note (per Codex R1 MINOR #3):** code dependencies as stated above — Item 5 (chart architecture) is independent of Item 7 (metrics wiring) at the COMPILE/TEST level. But the operator-witnessed gate verification of Item 5's hyp-rec chart wiring is EASIER to validate after Item 7's hypothesis-progress fix lands (suffix-bearing labels are easier to debug with a working progress card). Recommendation: keep code dependencies as written; sequence operator-witnessed gate verification of Item 5 chart wiring AFTER Item 7 hyp-progress fix is verified GREEN.

---

## §H Dispatch sequence + Codex chain expectations

### §H.1 Brainstorming phase

Codex chain expected 2-4 rounds. 7 items + cross-couplings + 16+ OQs are well-scoped and operator-confirmed; pre-Codex discipline now at 27 cumulative validations.

### §H.2 Writing-plans phase

Codex chain expected 3-5 rounds. Per-task acceptance criteria + SQL skeletons (Item 7 wiring fix) + JIT helper contract (Item 5) are likely Codex-find-bait surfaces. Pre-Codex 7-expansion + 3 NEW refinements (#8 SQL UNIT audit; #9 form-render anchor lifecycle; #4 refinement SQL column verification) BINDING.

### §H.3 Executing-plans phase

Codex chain expected 3-5 rounds (mirrors recent Phase 13 dispatch shapes). 28th cumulative C.C lesson #6 validation expected NOTABLE.

### §H.4 Operator-witnessed gate (post-merge)

S1 (inline): fast pytest + ruff + schema-unchanged-at-v21.
S2 (browser): `/dashboard` — confirm market-weather chart no-volume-axis-labels (Item 3); confirm no lightning glyph on watchlist (Item 4); confirm watchlist expand-collapse preserves thumbnail (Item 6); confirm any sub-A+ hyp-rec expand renders chart (Item 5 JIT); confirm hyp-progress card non-zero for "Sub-A+ VCP-not-formed" cohort (Item 7 fix).
S3 (CLI): `swing diagnose aplus-blockers --eval-runs 63` produces non-empty report against operator DB; operator reviews + provides input on threshold-loosening proposals (Item 1).
S4 (CLI): `swing diagnose metrics-wiring` produces audit table; operator reviews; confirms hyp-progress fix LIVE; confirms broader audit dispositions sane.
S5 (CLI): `swing patterns label-silver --pattern-class vcp ...` invocation with new contract; new keys persisted (Item 2; operator-paired session for re-label-corpus is V2-banked).

### §H.5 Post-merge housekeeping

Mirror T2.SB6c precedent:
- `--no-ff` merge of branch to main.
- Return report at `docs/phase13-t4-sb-return-report.md`.
- CLAUDE.md current-state line update.
- Orchestrator-context "Recent decisions and framings" update.
- Phase 13 main plan §H.3 row 13 appended.

---

## §I Forward-binding lessons inherited (BINDING for executing-plans phase)

### §I.1 Cumulative gotchas (CLAUDE.md) applicable to T4.SB

All 117+ cumulative gotchas honored. ESPECIALLY relevant for T4.SB scope:

- **§A.14 paired discipline** — only applies if schema changes are proposed. T4.SB is schema-UNCHANGED expected; if OQ-7.3 Option 7B (NEW `hypothesis_label_suffix` column) IS chosen, full paired discipline (schema CHECK + dataclass field + read-path mapper + write-path INSERT + 26+ paired tests in ONE commit) applies.
- **Form-render anchor lifecycle audit (NEW gotcha #13; Expansion #9 candidate BINDING)** — only applies if T4.SB introduces NEW hidden form anchors. Default scope: T4.SB does NOT introduce any new hidden anchors; if Item 5 architecture work surfaces a need (e.g., chart-scope POST handler), the 4-dimension audit applies.
- **HTMX OOB-swap partials drift gotcha** — DIRECTLY APPLIES to Item 6. Refinement banked: "OOB-swap context dict must include vm if partial dereferences vm.foo."
- **HTMX HX-Request + HX-Redirect failure surfaces** — applies if any new HTMX POST handlers land. Default scope: T4.SB does NOT introduce new POST handlers; if `swing diagnose prune-chart-cache` ships as a POST web surface (it should NOT per V1 scope), the failure-surface audit applies.
- **Matplotlib mathtext gotcha** — applies to Item 3 chart-rendering work. Verification: no `$`/`^`/`_`/`\` metacharacters introduced in volume-axis fix (the fix REMOVES tick labels; does NOT add text).
- **Windows cp1252 stdout safety** — applies to Item 1 + Item 7 diagnostic CLI subcommands. ASCII-only output enforced via subprocess-stdout-capture test.
- **F6 transient-empty defense at construction barrier** — applies to Item 5 JIT helper. `ChartRender(...)` construction barrier preserved (raises on empty bytes; cache row never blank-overwritten).
- **`Literal[...]` runtime-enforcement gotcha** — applies to Item 2 `_SilverLabelResponse` extension. `__post_init__` validation against explicit frozenset.
- **Service-layer ValueError wrap at CLI boundary** — applies to all Item 1 + Item 7 + Item 2 CLI subcommands.
- **`extended.pop(key, None)` gotcha** — applies if Item 7 fix involves envelope rewrites (Option 7B). Likely N/A under Option 7C recommendation.
- **Read-path mapping keeps pace with write-path** — applies if Option 7B is chosen (NEW column `hypothesis_label_suffix` → `_row_to_trade` mapper extension).
- **Server-recompute at POST (T3.SB3 R1 M#2 LOCK)** — applies if any new POST handlers consume operator input. Default scope: N/A.
- **Audit envelope empty-state uniformity** — N/A (no new audit envelopes).
- **Synthetic-fixture-vs-production-emitter shape drift** — applies to Item 1 + Item 7 diagnostic tests. Discriminating tests MUST plant production-shape fixtures (real `candidates` rows; real `trades` rows with operator-shape suffix labels).
- **Existing-field reuse audit before claiming new dataclass fields (NEW gotcha #10)** — applies to Item 2 `_SilverLabelResponse` + Item 6 `WatchlistRowVM` extensions. Verify NO existing field already serves the purpose.
- **Template-rendering surface audit (NEW gotcha #11)** — applies to Item 2 `/patterns/exemplars` template extension; verify rendering, not just dataclass population.
- **`date.fromisoformat()` cross-type-boundary discipline (NEW gotcha #12)** — applies to Item 7 broader audit if any new SQL-TEXT → Python-date conversions; default N/A.

### §I.2 Pre-Codex review expansions BINDING

- **Expansion #1** hardcoded-duplicate audit.
- **Expansion #2** brief-vs-spec source-of-truth + brief-vs-actual schema reality check.
- **Expansion #3** schema-CHECK-vs-semantic-contract gap audit.
- **Expansion #4 + NEW REFINEMENT** specific-scenario gotcha trace + SQL skeleton column verification.
- **Expansion #5** cross-section spec inventory grep.
- **Expansion #6** content-completeness audit.
- **Expansion #7 + NEW BOUNDARY CLARIFICATION** cross-row semantic SCOPE audit + scope-vs-unit boundary.
- **Expansion #8 (NEW BINDING)** per-aggregation-function UNIT audit on SQL skeletons.
- **Expansion #9 (NEW BINDING)** form-render anchor lifecycle audit 4-dimension.

### §I.3 Process discipline BINDING

- **NO Co-Authored-By footer** on any commit (~370+ cumulative streak).
- **`python -m swing.cli` from worktree cwd** (not bare `swing`).
- **ASCII-only on stdout-flowing CLI paths** + template narrative text.
- **TDD per task** (failing test → minimal impl → see pass → commit).
- **Edit tool for per-file edits**; Write tool reserved for net-new files.
- **Cite the discipline in commit messages** per cumulative precedent.

---

## §J Open questions (16+ OQs for operator-paired triage post-brainstorming)

### §J.1 Item 1 — 0 A+ candidates diagnostic

- **OQ-1.1 — diagnostic output format:** orchestrator-recommended CLI subcommand emitting markdown + CSV sidecar to `exports/diagnostics/`. Operator confirms? Alternative: fold into pipeline step output? Alternative: emit to research branch `research/notes/`?
- **OQ-1.2 — diagnostic time window:** orchestrator-recommended `--eval-runs N` parameter (default N=20; max N=100). Operator confirms? Alternative: full 63-run history default?
- **OQ-1.3 — post-diagnostic action threshold:** what fraction of blocking-criterion concentration would warrant IMMEDIATE threshold loosening proposal vs. just banking findings for research?
- **OQ-1.4 — production vs research branch placement:** orchestrator-recommended PRODUCTION (`swing/`). V2.1 §V branch posture argues research; operational urgency + the diagnostic's data-not-design nature argues swing. Operator confirms?

### §J.2 Item 2 — Path A labeler subagent contract widening

- **OQ-2.1 — subagent emit contract schema:** orchestrator-recommended schema at §B.2 (`rule_criteria` array of per-rule objects + `narrative` free text). Operator confirms? Alternative shapes (e.g., flat dict vs. array)?
- **OQ-2.2 — re-label existing 34 corpus exemplars OR forward-only:** orchestrator-recommended two-pronged ship + operator decides at execution time. Acceptable?
- **OQ-2.3 — V1 Path C backfill script retention:** orchestrator-recommended KEEP as fallback for future cohort-import scenarios. Operator confirms?

### §J.3 Item 5 — chart scope + JIT/flat-file architecture

- **OQ-5.1 — cache retention policy:** orchestrator-recommended R4 (manual prune CLI) + R1 default unbounded. Operator confirms? Alternative: R2 (retain N=5 pipeline_runs) or R3 (retain by age >60 days)?
- **OQ-5.2 — JIT cache-miss render latency budget:** orchestrator-recommended synchronous-JIT-no-timeout V1 default (worst case ~1-2s under cold-everything; acceptable for operator-paced workflow). Operator confirms? Alternative: synchronous-JIT-with-wallclock-timeout (~30 LOC more; placeholder + 202 on timeout); OR async-render with HTMX polling (V2 complexity)?
- **OQ-5.3 — pre-gen scope:** orchestrator-recommended "market_weather + position_detail + dashboard-top-5 watchlist ONLY" (NOT top-10; NOT hyprec_detail). Operator confirms? Alternative: keep top-10 OR include A+ hyprec_detail pre-gen if A+ pipeline lights up via Item 1 fix?
- **OQ-5.4 — re-run collision semantics:** orchestrator-recommended Option A (dashboard reader binds to one pipeline_run anchor; JIT writes match anchor). Operator framing literal-read suggests Option B (most-recent regardless of run). Which?
- **OQ-5.5 — chart-unavailable banner removal:** orchestrator-recommended KEEP as fallback for genuine errors. Operator confirms? Alternative: delete entirely once JIT lights up?

### §J.4 Item 7 — metrics wiring audit

- **OQ-7.1 — diagnostic-then-fix vs parallel:** orchestrator-recommended diagnostic ships FIRST (T-T4.SB.1) + fix ships SECOND (T-T4.SB.2). Acceptable? Alternative: parallel concurrent?
- **OQ-7.2 — broader audit scope:** orchestrator-recommended enumerate every metric surface in `swing/metrics/` + `swing/web/view_models/metrics/` + `swing/journal/stats.py` + dashboard cards. Operator confirms? Alternative: narrower (only currently-reporting-zero surfaces) OR broader (include `/journal` + `/trades/*` surfaces)?
- **OQ-7.3 — canonicalization-at-persistence-boundary fix location:** orchestrator-recommended Option 7C (READ-time prefix-match at dashboard query; NO schema change; preserves operator's per-trade suffix). Operator confirms? Alternative: Option 7A (canonicalize-at-persistence strips suffix; loses per-trade detail) OR Option 7B (NEW `trades.hypothesis_label_suffix` column; v22 schema bump; preserves detail + canonical name)?

### §J.5 Phase 13 closure marker + post-T4.SB sequencing

- **OQ-CL.1 — Phase 13 formal CLOSURE marker:** orchestrator-recommended CLAUDE.md + orchestrator-context updates at T-T4.SB.6 closer announcing "Phase 13 FULLY CLOSED — 12 of 12 sub-bundles SHIPPED". Naming OK?
- **OQ-CL.2 — Phase 14 trigger:** does T4.SB SHIPPED kick off Phase 14 (operator-defined), OR does the project transition to Applied Research branch focus per V2.1 §X tranche progression?
- **OQ-CL.3 — research-branch first-method-record selection:** schedule immediately post-T4.SB-SHIPPED (Item 1 diagnostic in hand), or hold for separate operator-paired session?

### §J.6 Cross-item additional OQs

- **OQ-X.1 — Items 3, 4, 6 — bundle as one Codex round vs. separate?** orchestrator-recommended ONE Codex round (bundled T-T4.SB.5 task). Operator confirms?

---

## §K Phase 13 closure marker

### §K.1 At T-T4.SB.6 SHIPPED + integration-merge

Update CLAUDE.md current-state line: replace `Phase 13 sub-bundle ship count: 11 of 11 (CLOSURE)` with `Phase 13 sub-bundle ship count: 12 of 12 (FULLY CLOSED)`.

Update `docs/orchestrator-context.md` "Currently in-flight work" + "Recent decisions and framings" to note Phase 13 SHIPPED + closed; T4.SB return report at `docs/phase13-t4-sb-return-report.md`.

Update `docs/cycle-checklist.md` with: quarterly re-run of `swing diagnose aplus-blockers` + `swing diagnose metrics-wiring`; archive prior outputs to `exports/diagnostics/archive/` pre-merge.

### §K.2 Phase 14 / research-branch transition

T4.SB SHIPPED transitions the project to **post-Phase-13 state**. The next dispatch decision is operator-driven per OQ-CL.2:
- **Path A** — Phase 14 dispatch (operator-defined; no commitment in T4.SB scope).
- **Path B** — Research-branch advancement (first-method-record selection per `research/phase-0-tasks.md` "Later (deferred)").
- **Path C** — Combination (Phase 14 + research-branch concurrent per V2.1 §V branch posture).

Phase 13 main plan §H.3 row 13 entry: `test_phase13_t4_sb_hypothesis_label_match_strategy_invariant` (cross-bundle pin row 13; GREEN-promoted at T-T4.SB.6).

---

## §L References

### §L.1 Primary substrate

- `docs/phase3e-todo.md:15-101` — 7 operator-confirmed triage items (BINDING).
- `docs/phase13-t4-sb-brainstorming-dispatch-brief.md` — orchestrator brief (this brainstorm responds to).

### §L.2 Phase 13 cumulative

- `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` — Phase 13 main spec (§7.3 reserved T4.SB scope).
- `docs/phase13-t2-sb6c-executing-plans-return-report.md` — T2.SB6c return report (§4.1 V1 simplifications inherited).

### §L.3 Architecture references

- `swing/evaluation/scoring.py:13-39` — `bucket_for` (Item 1).
- `swing/journal/stats.py:325` — `compute_hypothesis_progress_breakdown` (Item 7 CLI path).
- `swing/web/view_models/metrics/hypothesis_progress_card.py:404` — `build_hypothesis_progress_card_vm` (Item 7 dashboard path).
- `swing/metrics/cohort.py:40-96` — `list_trades_for_cohort` + `list_closed_trades_for_cohort` (Item 7 SQL).
- `swing/trades/entry.py:184-209` — `canonicalize_hypothesis_label` (Item 7 normalization helper).
- `swing/recommendations/hypothesis.py:259-285` — `_descriptive_label` (suffix builder).
- `swing/recommendations/hypothesis.py:416-435` — `_label_matches_hypothesis` (prefix-match helper).
- `swing/web/chart_scope.py:130-131` — chart-unavailable banner (Item 5).
- `swing/pipeline/runner.py:2280-2429` — `_step_charts` chart_renders write-through (Item 5).
- `swing/web/charts.py:332-366` — `render_market_weather_svg` (Item 3).
- `swing/web/charts.py:234-274` — `render_hyprec_detail_svg` (Item 3).
- `swing/web/templates/partials/watchlist_row.html.j2:9-17` — watchlist row partial (Items 4, 6).
- `swing/web/routes/watchlist.py:28-69` — watchlist row + expand routes (Item 6).
- `.claude/agents/pattern-labeler.md` — Item 2 subagent prompt substrate.
- `swing/cli.py:patterns_label_silver` + `_fire_claude_silver_label` (Item 2 invocation path).

### §L.4 Cross-branch references

- `research/phase-0-tasks.md` "Later (deferred)" — Item 1 → first-method-record selection dependency.

### §L.5 Cumulative gotchas + lessons

- `CLAUDE.md` at repo root (117+ cumulative gotchas).
- `docs/orchestrator-context.md` "Lessons captured" — Tranche B-ops canonicalization-at-persistence lesson; T2.SB6c form-render-anchor lifecycle lesson; full lesson-evolution chain.

### §L.6 Cross-bundle pin precedents

- `tests/data/test_phase13_t2_sb6c_cross_bundle_pin_row_12.py` — T2.SB6c precedent for parametrized cross-bundle pin file structure.

---

## §M Closing notes

### §M.1 Estimated dispatch scale

- ~3-6 hours operator-paced (per `feedback_time_estimates_overstated.md` ÷ 3-5x).
- ~6 sub-bundle commits + 2-4 Codex fix bundles + return report ≈ ~9-11 total commits.
- Net test delta ~+80-125 fast + 1 fast E2E.
- ZERO schema changes (unless OQ-7.3 Option 7B chosen at triage).
- ZERO new Schwab API calls (L2 LOCK preserved).

### §M.2 Brainstorming-phase Codex-review expectations

- 2-4 rounds expected.
- Likely Codex find-bait: (a) ambiguity in Option 7C vs Options 7A/7B framing (operator decides at OQ-7.3); (b) re-run collision Option A vs B (operator decides at OQ-5.4); (c) per-sub-bundle commit-granularity for Items 3+4+6 bundle.
- Pre-Codex 7-expansion + 3 NEW refinements (Expansion #4 + #8 + #9) BINDING; 28th cumulative C.C lesson #6 validation expected at this brainstorming phase.

### §M.3 Phase 13 closure context

T4.SB is the closer of Phase 13's 4-theme arc (T1 Schwab; T2 chart-patterns; T3 auto-fill; T4 usability). Phase 13 introduced v20 + v21 schema bumps, 9 detector pattern classes, the chart_renders cache substrate, the trades-to-pattern_evaluations + trades-to-candidates backlinks, 11 dispatched sub-bundles, ~370+ commits with ZERO Co-Authored-By footer drift, and 27 cumulative C.C lesson #6 validations. T4.SB closes the arc by addressing operator-supplied usability triage — the things that surfaced once the substrate landed but operator's daily workflow surfaced as friction.

End of spec.
