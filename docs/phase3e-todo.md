# Cross-Phase Operational Backlog

> **Filename note (2026-05-01):** this file is named `phase3e-todo.md` for historical reasons (it was created at the end of the Phase 3d walkthrough as the Phase 3e backlog). It has since accumulated cross-phase items (Phase 4 / 4.5 / 6-9 + standalone bundles + Tier-3 deferrals + research-branch followups). The filename is preserved to keep ~46 cross-references in shipped briefs valid; the canonical title is "Cross-Phase Operational Backlog." Not a commitment, just a trackable list.

> **Archive companion (2026-05-05):** SHIPPED + closed entries previously inline have moved to `docs/phase3e-todo-archive.md`. Fresh-orchestrator bootstrap reads only this active file; grep the archive on demand for historical context (commit hashes, prior dispatches). Retention discipline + archive-split trigger are documented in `docs/orchestrator-context.md` §"Maintenance: retention discipline."

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

### 3e.4 — Current price in hyp-rec expanded row (operator-surfaced 2026-05-08)

**Observed:** When a hypothesis-recommendation row on the dashboard is expanded (chevron click → `GET /hyp-recs/<ticker>/expand` → `partials/hypothesis_recommendations_expanded.html.j2`), the additional details panel does NOT include current price. Operator workflow: expand a hyp-rec to evaluate the trade decision; current-price context is needed alongside pivot, ADR, sector etc., but currently absent.

**Proposed fix:** Surface current price in the expanded panel. Mirrors the pattern already used in open-positions row (price_snapshot from PriceFetcher). VM `build_hyp_recs_expanded` already resolves the binding pipeline run; extend to also fetch the current price for the ticker (likely via the same `PriceCache` pathway the dashboard uses) and add to `HypRecsExpandedVM`. Template renders the price + stale-flag if applicable.

**Scope:** `swing/web/view_models/recommendations.py` (or equivalent VM) + `partials/hypothesis_recommendations_expanded.html.j2` + 1-2 discriminating tests (price renders when fetched; price omitted/marked stale when fetch fails). ~30-45 min standalone dispatch.

**Cross-references:**
- `swing/web/routes/recommendations.py:160` — `/hyp-recs/{ticker}/expand` route.
- `partials/open_positions_row.html.j2` — price + stale-flag rendering pattern to mirror.
- CLAUDE.md gotcha "OHLCV fetch scope = open-trade tickers ONLY" — does NOT apply here (this is current-price via PriceCache, not OHLCV).
- Watchlist row already shows price; same primitive likely available.

### 3e.5 — Daily management "updated today?" indicator on open-positions row (operator-surfaced 2026-05-08)

**Observed:** Phase 8 daily management surface lets operator log a daily snapshot OR event_log per trade per session, but the dashboard's open-positions table provides no at-a-glance signal of which trades have been touched today vs. which still need attention. Operator workflow: scan dashboard at end of day, must individually open `/trades/<id>` for each open trade to determine update status.

**Proposed fix:** Add a small icon or badge to each open-positions row indicating whether a `daily_management_records` row (`record_type IN ('daily_snapshot', 'event_log')` AND `is_superseded = 0`) exists for that trade with `review_date == action_session_for_run(now())`. Two-state visual: ✓ updated today / ⚠ not yet. Reuses Phase 8 §7.1 dashboard-tile plumbing (per `swing/data/repos/daily_management.py:list_open_position_active_snapshots`) — likely just adds a `has_update_today` boolean to `OpenPositionsRowVM`.

**Scope:** `swing/web/view_models/dashboard.py` (extend `OpenPositionsRowVM`) + `partials/open_positions_row.html.j2` (render badge after Ticker + state badge) + 2 discriminating tests (badge rendered when row exists; badge absent when not). ~30-45 min standalone dispatch.

**Cross-references:**
- Phase 8 §7.1 dashboard-tile feed (`list_open_position_active_snapshots`) — same predicate, scoped to "active snapshot for this trade today."
- `swing/evaluation/dates.py:action_session_for_run` — canonical session anchor.
- `partials/state_badge.html.j2` — existing badge-rendering pattern.

### 3e.6 — Auto-return to dashboard after daily management event submission (operator-surfaced 2026-05-08)

**Observed:** After submitting a daily management event/snapshot via the `POST /trades/<id>/daily-management/event` form on the trade-detail page, the response re-renders the detail page. Operator workflow at end of day is "tour open trades, log update on each, move to next" — current behavior requires manual navigation back to `/` after each submission.

**Proposed fix:** On successful submission, return `204 No Content` + `HX-Redirect: /` header (browser navigates to dashboard via htmx.js). Pattern: same as Phase 5 config page success-path (CLAUDE.md gotcha "HX-Redirect for HTMX success-path response"). Watch item: assert HX-Redirect target route resolves to 200 (Phase 6 lesson — TestClient verifies header but doesn't follow).

**Scope:** `swing/web/routes/trades.py` daily-management POST handler success-path + 2 discriminating tests (HX-Redirect emitted on success; target `/` resolves). ~15-30 min standalone dispatch.

**Cross-references:**
- CLAUDE.md gotcha "HTMX form-driven endpoints have two browser-only failure surfaces" (Phase 5 R1 M2).
- CLAUDE.md gotcha "HX-Redirect target route must be verified to exist" (Phase 6 I3).

### 3e.7 — Example entries beside premortem + pre-trade-thesis textareas (operator-surfaced 2026-05-08)

**Observed:** Trade entry form has free-text fields for pre-mortem + pre-trade thesis. New / occasional users may not know what an effective entry looks like; operator wants generic example text rendered alongside (not inside) the textareas to assist with filling them out.

**Proposed fix:** Add a side-panel `<aside>` to the right of each textarea showing 2-3 generic example entries (NOT trade-specific; static content). Operator preference: examples visible always, not toggle-shown. CSS layout: textarea + aside in a flex/grid container.

**Scope:** `partials/trade_entry_form.html.j2` (add aside elements with hard-coded example strings) + minor CSS for the side-panel layout in `static/style.css` + 1 discriminating test (asserts example text is rendered on entry form). ~30-45 min standalone dispatch. No VM changes (static template content).

**Cross-references:**
- `partials/trade_entry_form.html.j2` — current form rendering.
- `static/style.css` — flex/grid container patterns.

### 3e.8 — Sell-position indications for winning trades (INVESTIGATION; operator-surfaced 2026-05-08)

**Operator question:** What sell-side advisories / indications are surfaced for winning trades today, and what additions would close the doctrine gap? Framework currently emphasizes initial-stop discipline + trail-stop advisories (Phase 3d trail-MA at 20MA pre-+2R, 10MA post-+2R per Tier-3 #6 doctrine), but the affirmative "sell signal" surface for winners is less explicit. Tied to Tier-3 #6 (advisory state-machine + trade-maturity gating; operator-context.md deferred-with-tracking — MEDIUM-HIGH operational urgency; DHC currently approaching trail-MA decision territory).

**Investigation scope:**
1. **Survey current state.** Enumerate what sell-side / trim-side / take-profit advisories the dashboard currently surfaces (open-positions row advisory column; per-trade detail page Phase 8 daily-management `action_taken` enum; `swing/trades/advisory.py` rules). Identify gaps vs Minervini SEPA + Disciplined Swing Trader winner-management doctrine.
2. **Doctrine reconciliation.** Reference Minervini sell-into-strength + parabolic-extension-trim + 7-week-rule + violated-MA-on-volume rules. Reference Disciplined Swing Trader take-profit-into-strength + trail-tighten-after-+2R rules. Compare against Phase 8 maturity stages (pre_+1.5R / +1.5R-2R / +2R+ per Tier-3 #6 doctrine).
3. **Recommend additions.** Specific advisories to add (e.g., "20% advance in 1-3 weeks → consider sell-into-strength"; "violated 50MA on volume → exit"; "parabolic extension → trim 25-50%"). Per V2.1 §VII.F source-of-truth correction protocol if any addition would alter operational classification logic; per ordinary brief-then-dispatch path if it's only advisory-message extension.

**Scope estimate:** investigation 2-4 hours; subsequent implementation dispatch (if approved) 4-8 hours depending on rule count. Investigation can be orchestrator-thread OR dispatch (per Phase 4.5 brainstorm-dispatch threshold).

**Cross-references:**
- `docs/orchestrator-context.md` Tier-3 #6 (advisory state-machine + trade-maturity gating; deferred-with-tracking).
- `swing/trades/advisory.py` — current advisory rule surface.
- `reference/methodology/` — Minervini Trend Template + Disciplined Swing Trader transcriptions.
- Phase 10 metrics-dashboard `maturity_stage` cohort axis (`docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`).
- V2.1 §VII.F source-of-truth correction protocol.

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

### 3e.10 — Dark theme (operator-surfaced 2026-05-08)

**Observed:** Web UI is light-theme only. Operator wants dark theme available (operator preference + reduces eye strain in evening prep windows; aligns with most modern trader-facing tools).

**Proposed fix:** CSS-variable-driven theme system. Steps:
1. Refactor existing colors in `static/style.css` to CSS variables (`--bg`, `--fg`, `--accent`, `--badge-bullish-bg`, etc.) with light-theme defaults.
2. Add a `.dark` body class with dark-theme variable overrides.
3. Add a toggle UI element (likely in nav bar or status_strip) that flips the class + persists preference via `localStorage` (cookie if server-side persistence is preferred — Phase 5 user-config infrastructure could host it but localStorage is lighter).
4. Audit chart rendering — matplotlib chart PNGs are baked at pipeline time with light backgrounds; either regenerate per theme (heavy) or accept that charts stay light-themed against dark UI (acceptable V1).
5. Verify Phase 8 daily-management timeline rendering, watchlist tag colors, hyp-rec recommendation rows, advisory badges, state badges all read correctly under both themes.

**Scope:** ~2-4 hr standalone dispatch. CSS-heavy; minimal Python/template change. No VM changes.

**Cross-references:**
- `static/style.css` — current light-theme colors.
- `swing/web/templates/base.html.j2` — body element + nav bar.
- Phase 5 user-config infrastructure (`swing.config.toml` user-config) if server-side persistence preferred over localStorage.
- Operator's actual viewing environment (browser; OS-dark-mode preference) to inform whether to add `prefers-color-scheme: dark` media-query default.

### 3e.11 — CLI `swing review` help text leaks "Phase 6" internal nomenclature (operator-surfaced 2026-05-08)

**Observed:** `swing --help` and `swing review --help` show:
```
review       Phase 6: cadence review (daily / weekly / monthly...
```
Phase nomenclature is internal-development context, not operator-facing. The help text should describe the command's purpose self-contained.

**Locations** (per `grep -n "Phase 6" swing/cli.py`):
- `swing/cli.py:1174` — `"""Post-trade review (Phase 6).` (group docstring; surfaces in `swing review --help`)
- `swing/cli.py:1303` — `"""Phase 6: cadence review (daily / weekly / monthly Review_Log completion)."""` (subcommand; surfaces in `swing review cadence --help` AND `swing --help` group listing)

**Proposed fix:** Replace "Phase 6" leakage with self-descriptive text. Suggested:
- Group: `"""Post-trade review surface — log mistakes, process grade, and outcome attribution."""`
- Subcommand: `"""Cadence review — complete daily / weekly / monthly Review_Log entries."""`

**Scope:** 2-line change in `swing/cli.py` + 1 discriminating test asserting help text doesn't contain "Phase". ~10 min standalone fix; could bundle with any next CLI-touching dispatch. Audit other commands for similar phase-nomenclature leakage at the same time (`grep -n "Phase [0-9]\|Tranche" swing/cli.py`).

**Cross-references:**
- `swing/cli.py:1174` + `swing/cli.py:1303` — sites to fix.
- Pre-empt similar leakage in future CLI additions: per brief-drafting checklist, verify CLI help strings are operator-facing, not phase-nomenclature.

### 3e.12 — `swing tos-import` silent zero-result diagnosis — **SHIPPED 2026-05-09 at `a9541d2`**

> **Outcome:** Investigation-first dispatch (brief at `docs/tos-import-diagnostic-brief.md`) on worktree branch `tos-import-diagnostic` (BASELINE_SHA `25bbaa2`); 5 commits = 2 task-impl + 3 adversarial-fix; integration merge `a9541d2`. Investigation identified THREE mechanisms (originally orchestrator analyzed two; implementer surfaced the third empirically): (A) `Exec Time` column in real Schwab/TOS export (parser was looking for `Date`/`DATE`); (B) signed Qty (`+7` BUY / `-3` SELL) tripped `qty <= 0` guard; (C) M/D/YY date format vs journal's ISO `entry_date` blocked match-query even after (A)+(B). Operator-confirmation gate PASSED. Fix scope expanded mid-dispatch by operator clarification ("the whole point of reconciliation is to check for existence AND correct values") — broadened §3.1 from extraction-only to full-pipeline reconciliation tests. Adversarial review chain: R1 0/4/2 → R2 0/2/2 → R3 0/1/2 → R4 NO_NEW_CRITICAL_MAJOR (convergent shape; 4→2→1→0 majors). Test count 2090 → 2099 (+9; ruff baseline 78 preserved). New `_normalize_date()` helper + `FillDecision` dataclass + `tests/fixtures/tos/real-world-2026-05-08.csv` real-world fixture. New `--verbose` flag surfaces per-section row counts + per-fill price-comparison output. Post-merge smoke test against operator's actual CSV: `matched=4, already-reconciled=2, price-mismatch=0` (4 OPEN fills LAR/CVGI/VSAT/YOU reconciled with journal entry_prices matching; SGML round-trip routed to already-reconciled). Per retention discipline, this entry stays in active until next phase ship; original investigation content retained below for historical reference.

### Original entry (2026-05-08; pre-dispatch; superseded by SHIPPED outcome above)

`swing tos-import` silent zero-result diagnosis (INVESTIGATION; operator-surfaced 2026-05-08)

**Observed:** Operator ran `swing tos-import --csv "...\2026-05-08-AccountStatement.csv"` (with and without `--dry-run`). Output:
```
Cash: 0 new, 0 duplicate
Fills: matched=0, already-reconciled=0, price-mismatch=0, unmatched OPEN=0, unmatched CLOSE=0
```
Every counter is zero. Operator has open trades + at least one Phase 8 stop-change today (DHC) so the CSV almost certainly contains transactions. The CLI provides NO indication of WHY the result is empty — parser silent-fallback OR file structure changed OR everything-already-reconciled-and-empty-CSV-section all collapse to the same output.

**Possible mechanisms (NON-exhaustive; investigation must disambiguate):**

1. **CSV section-parser silent failure.** TOS Account Statement CSVs are multi-section (Cash Balance, Account Order History, Account Trade History, Profits And Losses, Forex Account Summary, etc.). The parser at `swing/journal/tos_import.py` looks for specific section headers; if Schwab/TOS renamed a section header in a recent export-format update, the parser silently produces 0 rows for that section. Pattern complement to existing CLAUDE.md gotcha "TOS-import TRD-as-withdrawal" + "Excel-quoted REF cleanup" (both 2026-04-30); same family — TOS export format drift breaking parser silently.
2. **Empty trade window in this specific export.** If operator exported only a date range with no fills (e.g., 1-day window with no trades on 5/8), parser correctly produces 0. Unlikely given operator's open trades + Phase 8 stop-change activity, but verify.
3. **All transactions already reconciled.** Existing journal state already includes all CSV transactions; `matched=0` because matched-already-skipped, but `already-reconciled` should then be > 0 (it's also 0). This rules out the "everything already done" hypothesis — parser ISN'T finding rows at all.
4. **Encoding / line-ending / BOM mismatch.** TOS CSVs sometimes have UTF-16 BOM or CRLF variants; if the parser splits on a different newline pattern than the export uses, rows silently dropped.
5. **Filename-date mismatch with parser's date-anchoring logic.** Some TOS parsers anchor to filename date; if the CSV content's session date doesn't match the filename date, rows could be filtered.

**Investigation steps:**

1. **Open the actual CSV** (`thinkorswim/2026-05-08-AccountStatement.csv`) and verify structure manually: does it contain a trades section? How many rows? What section headers does it use?
2. **Add diagnostic logging** to `reconcile_tos` (or a new `--verbose` flag on the CLI) that reports: total bytes parsed; section headers detected; rows-per-section count; sample row from each section. Operator-facing observability — converts silent-zero into observable-zero-with-context.
3. **Run synthetic-fixture comparison.** `tests/fixtures/tos/synthetic-tos.csv` is the test fixture; verify it currently parses correctly (`pytest tests/journal/test_tos_import.py`). If parser works on synthetic but fails on operator's real export, diff the structure.
4. **If section-header drift confirmed:** add per-section "found 0 rows in section X" warnings to the CLI output even on success. Pre-empts future silent-fail.
5. **Bonus:** consider extending the CLI report with "Sections parsed: Cash=1 (0 rows), Trades=1 (0 rows), Forex=0 (skipped)" so operator can distinguish "section absent" from "section present but empty."

**Scope:** ~1-2 hr investigation + 30-60 min hardening dispatch (logging, parser-error visibility). Could be bundled into a single dispatch if root-cause is clear from initial CSV inspection.

**Cross-references:**
- `swing/journal/tos_import.py` — parser code.
- `tests/fixtures/tos/synthetic-tos.csv` — synthetic fixture (CLAUDE.md gotcha "Synthetic-fixture coverage gap can mask real-world data shape bugs" 2026-05-01 — same family).
- CLAUDE.md gotcha "TOS-import TRD-as-withdrawal fix + Excel-quoted REF cleanup" (2026-04-30) — prior parser breakage on real-world export format.
- `thinkorswim/2026-05-08-AccountStatement.csv` — the actual CSV that triggered this.
- 2026-04-30 TOS reconciliation depth follow-ups bundle (BUNDLED into Phase 9 brainstorm at `31ee51c`) — Phase 9 will redesign the reconciliation surface; this investigation may inform Phase 9 writing-plans (or get subsumed if Phase A of Schwab API ships first).

### 3e.13 — Top-nav "Reviews" link to `/reviews/pending` (operator-surfaced 2026-05-09)

**Observed:** The base template's nav bar (`swing/web/templates/base.html.j2`) renders Dashboard / Watchlist / Journal / Pipeline / Config — but NO Reviews link. The Phase 6 review list view at `/reviews/pending` is reachable only via direct URL OR via the post-review-complete HX-Redirect (per Phase 6 I3 fix). Operator workflow: there's no obvious path from the dashboard to the daily/weekly/monthly cadence reviews surface.

**Proposed fix:**
1. Add `<a href="/reviews/pending">Reviews</a>` to the base.html.j2 nav between Journal and Pipeline (workflow-aligned position — review is a journal-adjacent activity).
2. **Optional enhancement (V1.5):** add a count badge `Reviews (N)` where N = count of pending Review_Logs (mirror the existing "needs review" badge pattern shipped in Phase 6 — `swing/web/view_models/dashboard.py` has `pending_reviews_count` or similar field already).

**Scope:**
- V1 (link only): 1-line template addition + 1 discriminating test (assert nav contains "Reviews" + correct href). ~10-15 min.
- V1.5 (link + count badge): + base-layout VM extension to surface count + base.html.j2 conditional render. ~30-45 min if VMs need extension; possibly ~15 min if `pending_reviews_count` already lives on a base-layout-friendly VM.

**Cross-references:**
- `swing/web/templates/base.html.j2` — nav bar location.
- `swing/web/routes/reviews.py` (or wherever `/reviews/pending` route lives) — confirms route exists.
- Phase 6 archived follow-up "Cadence card lacks clickable 'Complete review' link" (in `docs/phase3e-todo-archive.md`) — RELATED but different gap; that's about cadence card → completion form on dashboard; this is about top-nav → review list view.
- CLAUDE.md gotcha "base.html.j2 is shared — new vm.foo field requires adding to EVERY base-layout VM" — applies if V1.5 (count badge) requires a new base-layout-dereferenced field.

**Bundling note (2026-05-09):** This item is the same size profile + UX-polish theme as 3e.5 / 3e.6 / 3e.11 (the in-flight polish-bundle-2026-05-09 dispatch at brief `1957946`). If dispatch hasn't fired yet, consider expanding the brief to a 4-item bundle. Otherwise picks up as an independent ~15-min standalone after the polish bundle ships.

### 3e.14 — Cadence card "Complete review" inline link (operator-surfaced 2026-05-09; lifted from archived Phase 6 V1 follow-up)

**Observed:** Cadence cards on the dashboard (rendered by `swing/web/templates/partials/cadence_cards.html.j2`) display period + scheduled/completed status but have NO clickable link to the completion form when `card.is_pending`. Operator must navigate via direct URL OR (with 3e.13 in flight) via top-nav Reviews → list view → click into the matching review. The cadence card itself, where the pending status is visible, has no direct action surface. **This entry was archived as a Phase 6 V1 follow-up 2026-05-04 + lifted back to active 2026-05-09 because operator surfaced the gap during the polish-bundle-2026-05-09 dispatch and confirmed it remains valid.**

**Proposed fix:**
1. Extend `CadenceCardVM` (`swing/web/view_models/dashboard.py:292`) with `review_id: int` field (currently absent — archived fix sketch assumed `card.review_id` existed but VM doesn't carry it).
2. Populate `review_id=row.id` in the construction site at `swing/web/view_models/dashboard.py:1016-1023`.
3. Add link in template `partials/cadence_cards.html.j2`: `{% if card.is_pending %}<a href="/reviews/{{ card.review_id }}/complete">Complete review</a>{% endif %}`.
4. 2 discriminating tests: link rendered when card is_pending; link absent when completed.

**Scope:** ~15-20 min standalone; pairs naturally with 3e.13 (top-nav Reviews link) since both surface review reachability gaps from the dashboard.

**Cross-references:**
- `swing/web/templates/partials/cadence_cards.html.j2` — current card template (no link).
- `swing/web/view_models/dashboard.py:292-306` — `CadenceCardVM` definition (needs `review_id` field).
- `swing/web/view_models/dashboard.py:1016-1023` — construction site (populate `review_id=row.id`).
- `swing/web/routes/reviews.py` (or wherever) — `/reviews/{id}/complete` route confirmed Phase 6 R5 I3.
- 3e.13 (in-flight bundle) — top-nav reachability; this is the per-card direct-action surface.
- Archived entry at `docs/phase3e-todo-archive.md:736` — original 2026-05-04 capture.

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

### Phase 8 — Daily_Management + MFE/MAE precision — **SHIPPED to main 2026-05-07 at `ddfdfcb`**

> **Brainstorm outcome:** Dispatched 2026-05-06; brief at `docs/phase8-daily-management-brainstorm-brief.md` (`e9ce5a3`). Spec at `docs/superpowers/specs/2026-05-06-phase8-daily-management-design.md` (875 lines; commits `c2507d3..c954eef`; 5 substantive Codex rounds + R5 confirmation → `NO_NEW_CRITICAL_MAJOR`; convergent chain per Phase 7 Sub-B lesson — each round caught fix-introduced regressions, not adversarial thrash). Three highest-leverage locked decisions: (1) **single table** `daily_management_records` with `record_type` discriminator + validator-level operation-contextual requiredness; (2) **tier-upgrade additive with audit trail** via `is_superseded` flag + `superseded_by_record_id` FK; (3) **authoritative-source precedence ladder** anchoring `trades.current_stop` as LIVE truth. Capture cadence: new pipeline step `_step_daily_management` after `_step_evaluate`; UPSERT key `(trade_id, data_asof_session, mfe_mae_precision_level)` via SELECT-then-UPDATE-or-INSERT (NOT SQLite REPLACE per R4 fix); GAP-FLAGGED no auto back-fill. `trail_MA_candidate_price` = 21-day SMA at session close with per-row `trail_MA_period_days` stamp; `planned_target_R` lives on trades table (pre-trade-locked discipline). Phase 8 spec §11 surfaces 4 capture-needs feedback for Phase 9 brainstorm.

> **Writing-plans outcome:** Dispatched 2026-05-07; brief at `docs/phase8-daily-management-writing-plans-brief.md` (`206b900`). Plan at `docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md` (4140 lines; commit `17b1845`; 8 substantive Codex rounds + R9 confirmation → `NO_NEW_CRITICAL_MAJOR`; new high-water mark for round count in this project; tapered finding count 5→5→3→5→2→1→2→1→0; convergent chain per Phase 7 Sub-B + Phase 8/9 brainstorm lesson family — most R3+ findings were fix-introduced regressions or detail-cascade follow-ups). 15 active tasks; test count projection +55 to +100 fast tests (planner-projected subtotal +79; range biased high per Phase 6 lesson); estimated executing-plans dispatch effort ~13-15 hours. Three highest-leverage plan decisions: (1) **§A.1 service-call-inside-transaction empirical resolution** — Phase 8's `record_event_log` calls REPO-level `swing/data/repos/trades.py:update_stop_with_event` (NOT service-level `swing/trades/stop_adjust.py:update_stop_with_event` at line 105 which opens its own `with conn:` block); `linked_trade_event_id` resolved via TRADE-SCOPED max-id-after-insert pattern (NOT `last_insert_rowid()` which can return zero/stale on no-op early-return); defense-in-depth validator boundary rejects no-op stops + stale prior_stop re-read; (2) **§A.0 migration rename 0015→0016** because 0015 was already shipped as Finviz V1 — orchestrator-brief miss caught as Critical R1 by implementer; new `_phase8_backup_gate` function wired at `current_version == 15 AND target_version >= 16`; pre-Phase-8 expected table set redefined as `(PHASE7_EXPECTED_TABLES - {"exits"}) | {"fills", "finviz_api_calls"}` per empirical v15 schema; (3) **§A.2 V1-defer CLI** (web-only) per Phase 6 review surface precedent; V2 follow-up queued separately. CLI scope decision locked V1-defer. T7.0 operator-witnessed verification gate is BINDING per Phase 5/6 lesson family. Executing-plans dispatch queued (worktree-isolated; subagent-driven-development; marker-file workflow; targets schema_version 16; expected fast-suite range 1996-2041 tests). Per retention discipline, this entry stays in active until next phase ship.

### Original queued entry (2026-05-04; pre-design-lock; superseded by SHIPPED brainstorm above)

**Bundle:** Daily_Management snapshot/event_log + per-day MFE/MAE computation via OHLCV cache + precision-flag hierarchy.

**Scope:**
- New `daily_management_records` table: `management_record_id, trade_id, record_type (daily_snapshot/event_log), review_date, current_price, current_stop, open_R_effective, portfolio_heat_contribution_dollars, MFE_to_date_R, MAE_to_date_R, thesis_status` + event_log additional fields (prior_stop, stop_changed, stop_change_reason, action_taken, emotional_state, rule_violation_suspected).
- MFE/MAE precision per v1.2 §8.6: `intraday_exact / intraday_estimated / daily_approximate`. We have OHLCV cache → daily_approximate ships immediately; intraday_estimated when intraday data sourced.
- Web dashboard tile: per-open-trade MFE/MAE-to-date.

**Estimated dispatches:** 2-3.

**Cross-references:**
- `reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md` §7.7 (Daily_Management), §8.6 (MFE/MAE), §10.3 (In-Trade Review workflow).
- Existing OHLCV cache: `swing/data/ohlcv_archive.py` (Phase 3 OHLCV consolidation; 696 tickers consolidated 2026-04-30).
- Existing advisory infrastructure: `swing/trades/advisory.py` (Phase 3d SMA-aware advisories) — extends naturally.

### Phase 9 — Risk_Policy entity + reconciliation depth — **brainstorm SHIPPED 2026-05-06 at `31ee51c`**

> **Outcome:** Brainstorm dispatched 2026-05-06; brief at `docs/phase9-risk-policy-reconciliation-brainstorm-brief.md` (`d89b74b`). Spec at `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (1090 lines; commits `bc6da37..31ee51c`; 4 substantive Codex rounds + R5 confirmation → `NO_NEW_CRITICAL_MAJOR`; convergent chain — every R2/R3/R4 finding was an R-N-1-fix-introduced regression). Three highest-leverage locked decisions: (1) **per-policy-snapshot risk_policy versioning** with `is_active` + `superseded_by_policy_id` dual-column pattern (per Phase 8 `is_superseded` lesson application); (2) **Phase 7 state machine UNTOUCHED** — reopen review surface via query-side JOIN against `reconciliation_discrepancies.material_to_review = 1 AND resolution = 'unresolved'`, NOT a schema flag (R1 Major #4 catch — review_log is cadence-period-grain not trade-grain); (3) **`risk_policy` canonical post-Phase-9 source-of-truth** — `swing.config.toml` becomes startup-mirror with divergence banner + explicit `swing config policy import-from-toml` ratification (preserves audit-trail integrity). 5 new tables: `risk_policy`, `reconciliation_runs`, `reconciliation_discrepancies`, `hypothesis_status_history`, `account_equity_snapshots`. Phase 6 review_log gets ONE column add (`risk_policy_id_at_review_completion`). 10 discrepancy_type enum values (close_price_mismatch / stop_mismatch / position_qty_mismatch / cash_movement_mismatch / sector_tamper / snapshot_mismatch / unmatched_open_fill / unmatched_close_fill / entry_price_mismatch / equity_delta); `material_to_review` is CLASSIFICATION (not workflow trigger). TOS reconciliation depth bundle SUBSUMED — 3 queued gaps + new Gap 4 (cash_movement) mapped to discrepancy_type with locked JSON shapes. Sector/industry tamper hardening: BOTH schema-side (reserved enum value) + route-layer (writing-plans territory). Schwab API Phase A coordination: `source` enum reserves `schwab_api`; no Schwab-specific columns in V1; boundary contract specified for V2. 6 open questions surfaced with implementer recommendations; orchestrator concur on all 6. Spec §11 enumerates capture-needs feedback for Phase 10 writing-plans (LIVE policy reads vs at-trade-time policy reads; account_equity_snapshots resolution ladder schwab_api > tos_csv > manual > PROVISIONAL fallback). Writing-plans dispatch queued (Phase 8 writing-plans first per execution order 8 → 9 → 10). Per retention discipline, this entry stays in active until next phase ship.

### Original queued entry (2026-05-04; pre-design-lock; superseded by SHIPPED brainstorm above)

**Bundle:** Lift `swing.config` risk fields to versioned DB Risk_Policy entity + integrate the queued TOS-reconciliation-depth bundle (close-fill price mismatch + stop-order reconciliation + position-qty reconciliation) into a structured Reconciliation_Run / Reconciliation_Discrepancy framework.

**Scope:**
- New `risk_policy` table: `policy_id, effective_from, effective_to, is_active, max_account_risk_per_trade_pct, max_concurrent_positions, max_portfolio_heat_pct, max_sector_concentration_positions, consecutive_losses_pause_threshold, drawdown_circuit_breaker_enabled` (default false). Existing `swing.config.toml` values become the seed of policy_id=1.
- New `reconciliation_runs` + `reconciliation_discrepancies` tables. Existing `tos_import` reconcile flow refactors to write Reconciliation_Run rows + Discrepancy rows for each mismatch (close-price, stop, position-qty, cash). Material-to-review semantics: discrepancies on reviewed trades reopen the review.
- Subsumes the standalone "2026-04-30 TOS reconciliation depth follow-ups (BUNDLED)" entry above — when Phase 9 ships, the queued bundle's three gaps (close-price + stop + position-qty) ship as part of Phase 9, not as a separate dispatch.

**Estimated dispatches:** 3-4.

**Cross-references:**
- `reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md` §7.8 (Risk_Policy), §7.9 (Reconciliation_Log), §10.5 (Reconciliation Workflow).
- This document's "2026-04-30 TOS reconciliation depth follow-ups (BUNDLED)" entry above.
- Existing config: `swing/config.py` + `swing.config.toml`.
- Existing TOS import: `swing/journal/tos_import.py`.

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

### Original queued entry (2026-05-04; pre-design-lock; superseded by SHIPPED V1 above)


Operator-surfaced 2026-05-04. Replace the manual-CSV-export-to-`data/finviz-inbox/` ingestion workflow with programmatic Finviz Elite API access (https://elite.finviz.com/api_explanation). Concurrent goal: improved structured logging of all ingestion calls (request params, response sizes, screen versions, rate-limit consumption, failure modes) — current pipeline logging is per-step but not data-source-instrumented.

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
