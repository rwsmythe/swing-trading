# Cross-Phase Operational Backlog

> **Filename note (2026-05-01):** this file is named `phase3e-todo.md` for historical reasons (it was created at the end of the Phase 3d walkthrough as the Phase 3e backlog). It has since accumulated cross-phase items (Phase 4 / 4.5 / 6-9 + standalone bundles + Tier-3 deferrals + research-branch followups). The filename is preserved to keep ~46 cross-references in shipped briefs valid; the canonical title is "Cross-Phase Operational Backlog." Not a commitment, just a trackable list.

---

## Dashboard / UX enhancements

### 3e.1 — Mark-to-market on Account card — **SHIPPED 2026-04-26** (commit `2b5cded`, QoL bundle Session 1)

**Observed:** The dashboard Account card shows `current_equity` (starting equity +
realized P&L + net cash). This is "settled cash" semantics, not "total account
value including unrealized P&L." On open positions with unrealized gains/losses,
the Account card doesn't reflect that.

**Proposed:** Add an "Unrealized P&L" line item under the Account card showing
`sum((snap.price - entry) * remaining_shares)` over open positions. Keep the
existing equity figure (it's important for position-sizing math), but give the
operator a mark-to-market view alongside.

**Rationale:** Brokerage apps show total account value; absence here is
surprising and easy to misread as "my P&L isn't moving."

**Scope:** ~1 template change + VM field. Phase 2 untouched.

---

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

### 3e.3 — `POST /prices/refresh` also clears OHLCV breaker — **SHIPPED 2026-04-26** (commit `5b56a2d`, QoL bundle Session 1)

**Observed:** The /prices/refresh button bypasses PriceCache's circuit breaker
but doesn't touch OhlcvCache. If the OHLCV breaker is tripped, the operator
sees the "SMA advisories unavailable" banner with no interactive way to force
a retry.

**Proposed:** Extend the prices-refresh handler to also call
`ohlcv_cache.reset_circuit_breaker()`. OR add a separate `/ohlcv/refresh` button.

**Rationale:** Operator UX parity. Currently the OHLCV breaker only clears on
the 60s cooldown timer.

**Scope:** 1 route change + test. Phase 2 untouched.

---

## Watchlist UX bugs

### 3e.4 — Watchlist entries can expand but cannot collapse — **SHIPPED 2026-04-26** (commit `2c04aa2`, QoL bundle Session 1)

**Observed:** Clicking a watchlist row expands it to show details. Clicking the
expanded row does nothing — no toggle/collapse. Operator has to refresh the
page to reset the view.

**Proposed:** Make the expand trigger a toggle (click again to collapse), OR
add an explicit collapse affordance (close X in the expanded panel).

**Scope:** 1 template + HTMX swap pattern change. Phase 2 untouched.

---

### 3e.5 — Stale placeholder text in expanded watchlist entries — **SHIPPED 2026-04-26** (commit `d5b076c`, QoL bundle Session 1)

**Observed:** Expanded watchlist entries contain the literal string:

> Log entry (CLI — 3b adds button)

This was a Phase 3a/3b placeholder for a "Log entry" button that would let the
operator annotate a watchlist row. The button was scoped to Phase 3b but never
shipped; the placeholder text was left in.

**Proposed:** Either ship the button (open a modal, insert a note row to
watchlist_notes table, display inline), OR remove the placeholder text.

**Recommendation:** Remove the placeholder for now; revisit the annotation
feature in a later phase when the need is clearer.

**Scope:** Simplest case — 1 template edit. Or 2 route + 1 migration + 1
template if we ship the button.

---

### 3e.6 — No graph pattern shape estimation — **BRAINSTORM SHIPPED 2026-04-26** (spec at `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`, commit chain `9583f19..081f689`); writing-plans dispatch queued. V1 scope = `flag_pattern` only; other patterns deferred to V2+. See "2026-04-26 chart-pattern flag-v1 brainstorm follow-ups" section below.

**Observed:** The app computes VCP tightness via range-CV and bar-ratio checks,
but doesn't emit a structural classification of the chart pattern (flag,
pennant, flat base, tight channel, cup-with-handle, etc.). The operator has to
chart-read each ticker manually to classify.

**Proposed:** Add a pattern classifier that runs on candidates and outputs a
shape tag. Minimal viable:
- Flat base: ≥ 5 weeks, range ≤ ~15%
- Flag: < 3 weeks, range tight, prior trend steep
- Pennant: similar to flag but converging ranges
- Cup-with-handle: multi-month U-shape + shallow pullback near pivot
- Tight channel: 2+ weeks of converging highs/lows

Render as a flag tag on the watchlist + briefing, same mechanism as `TT✓ VCP✓ A+`.

**Rationale:** Chart-reading is the high-value operator step; surfacing a
suggested pattern reduces cognitive load and provides a falsifiable claim
("model says flag — do I agree?").

**Scope:** Significant. New module under `swing/evaluation/patterns/`, likely 50–100
test cases over real historical examples, new flag_tag dictionary. Phase 2
carve-out probably required.

**Reference pattern images already in repo** (correct paths):
- `reference/images/flag_pattern.png`
- `reference/images/pennant_pattern.png`
- `reference/images/tight_channel_flat_base.png`

---

## Summary

| ID | Area | Complexity | Phase 2 carve-out? | Status |
|---|---|---|---|---|
| 3e.1 | Unrealized P&L on Account card | Low | No | **Shipped 2026-04-26** |
| 3e.2 | Partial-exit realized in journal total | Low | No | Open |
| 3e.3 | Prices-refresh clears OHLCV breaker | Low | No | **Shipped 2026-04-26** |
| 3e.4 | Watchlist collapse toggle | Low | No | **Shipped 2026-04-26** |
| 3e.5 | Remove stale "Log entry" placeholder | Trivial | No | **Shipped 2026-04-26** |
| 3e.6 | Chart pattern shape estimation | High | Yes | **Brainstormed 2026-04-26**, writing-plans queued |

3e.1, 3e.3, 3e.4, 3e.5 shipped in QoL bundle Session 1 (2026-04-26). 3e.2 remains
the only small open item from the original Phase 3d backlog. 3e.6 has a complete
spec; implementation is gated on operator decision to dispatch plan + execute.

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

## 2026-04-25 S&P 1500 study follow-ups

Items surfaced during the S&P 1500 universe expansion study (commits `a921e4b..4a372da`) that were deliberately deferred per scope discipline.

- **Newcombe interval on (S&P 1500 1× rate − SPX+NDX 1× rate).** Tier classification used point-estimate uplift per pre-registration; the per-rate Wilson CIs overlap, so a formal difference-of-proportions inference is open. The Newcombe interval would be the proper instrument. Nice-to-have refinement for tighter inference; not load-bearing for the descriptive Tier 2 finding.
- **Multi-window characterization on S&P 1500.** The Tier 2 result is a single-window observation. Rolling-window characterization (e.g., overlapping 6-month windows) would test rate stability across regimes within the broader 2024-04 → 2026-04 period. Operator-decision gated.
- **5× capital cell on S&P 1500.** Pre-registration scoped the study to 1× only (operator's actual capital). A 5× cell would complete a 4-cell matrix analogous to the candidate-sparsity diagnostic. Deferred per capital-sensitivity disposition (capital is informational, not workflow-changing).
- **Capital-binding-on-mid-caps interpretive finding (informational, not a follow-up task).** Production-gated risk_feasibility on S&P 1500 1× was 9.65% (vs SPX+NDX 18.62%, Russell 6.91%). At the operator's $7,500 capital, mid-cap universes fit the sizing budget BETTER than large-cap universes. Worth surfacing in any future operator-facing universe-decision conversation.
- **Byte-identical re-run with patched diagnostic_run for clean-checkout artifact proof.** D5 patch added `git_dirty` field to manifest for FUTURE runs; THIS D3 run's clean-checkout assertion remains procedural. Adversarial review accepted; orchestrator can request stronger artifact-level proof if needed. Low priority.

---

## 2026-04-25 — Proposed next study (SHIPPED 2026-04-25)

- ~~**Per-criterion binding-constraint analysis on operator's actual Finviz pool.**~~ SHIPPED. See `research/studies/finviz-pool-binding-constraints.md` for findings.

---

## 2026-04-25 Finviz-pool study + hypothesis-label follow-ups

Items surfaced during the Finviz-pool per-criterion analysis (commits `618cb9c..6ca6a40`) and trade hypothesis label Phase 3e change (commits `1cec5df..123f83c`).

### From Finviz-pool study:

- ~~**Watch-staging UI surface for near-A+ defensible candidates.**~~ SUBSUMED 2026-04-25 by hypothesis recommendation engine (commits `b24506b` → `fe270a6`). Near-A+ defensible candidates surface in the dashboard "Hypothesis-driven recommendations" section under the "Near-A+ defensible: extension test" hypothesis. SLDB/UCTT-class tickers automatically appear there when they recur as watch-bucket candidates failing only `proximity_20ma`.
- **Longer-window Finviz-pool re-run after 30-60 days more data accumulates.** Same study module (`research/finviz_pool_analysis/`); just re-execute. The 8-day single-ticker SLDB-population caveat resolves naturally as more daily Finviz CSVs accumulate. Estimated 30 minutes once enough data exists; useful for operator to confirm or revise the descriptive findings.
- **Path-resolution policy for renamed-rejected CSVs.** Implementer flagged: 1 evaluation_run skipped because its CSV was renamed to `data/finviz-inbox/rejected/finviz16Apr2026.rejected-20260419T064456.csv`. Strict literal-basename match was implemented; stem-prefix match could include rejected runs. **Defer indefinitely.** 1 run affected; semantics could go either way; not load-bearing.
- **Single-ticker A+ population caveat.** All 3 A+ rows in the 8-day snapshot were SLDB on 2 dates. Inherent limitation of a small window; resolves with longer-window re-run above. Not a follow-up task; documented limitation.

### From hypothesis-label Phase 3e change:

- ~~**Backfill of historical trades (VIR).**~~ DONE 2026-04-25. After `swing db-migrate` applied schema 7, ran `UPDATE trades SET hypothesis_label = 'sub-A+ VCP-not-formed test (proximity_20ma + tightness fails); inaugural trade test' WHERE id = 1;` against production DB. n=1 historical trade now labeled.
- **Future formalization to controlled vocabulary.** Free-text initially per operator confirmation; once 5+ labeled trades reveal natural categories, formalization to enum + validation is a follow-on. Not urgent.

### Cross-cutting: Post-hoc trade analysis CLI tool

- ~~**`swing trade analyze <trade_id>` retrospective tool.**~~ SHIPPED 2026-04-25 (commits `375344f` cross-contaminated + `2815daa` + `4c2fdbd` → `d5b1753`). VIR verification reproduces manual case-study output exactly. Handles both production-recommended and manually-sourced trades.

### Operational hygiene

- ~~**Weekly DB backups during the first pipeline run of the calendar week.**~~ SHIPPED 2026-04-25 (commits `4a565c6` → `1540489`). WAL-safe via `sqlite3.Connection.backup()` API. Auto-backup verified working in operator's mid-session db-migrate.

### Chart-pattern algorithm framing note (cross-reference)

Per `docs/orchestrator-context.md` 2026-04-25 binding-constraint analysis: chart-pattern algorithm (Phase 3e §3e.6) is for **encoding qualitative chart-pattern input into structured feedback-loop data**, NOT for throughput acceleration (operator can manually assess at saturation rate). Important addition; not urgent. Multi-session copowers cycle when ready. Hypothesis-label free-text absorbs qualitative chart-pattern input as interim solution.

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

- **(2026-04-30 hypothesis_label web-form gap) ARCHITECTURAL: web entry form does not capture `hypothesis_label`.** Latent since 2026-04-25 hypothesis-recommendation-engine ship; surfaced by operator's CC trade entry on 2026-04-30 (per-row "Take this trade" button on hyp-recs expansion). **Concrete failure mode:** every web-form trade entry persists `hypothesis_label = NULL` (then empty string at canonicalization) → progress count never increments → tripwire never fires from web entries. Verified in `swing/web/`: ZERO references to `hypothesis_label` in views, view_models, routes, templates. CLI has full pre-fill machinery (`swing/cli.py:415-501`); web has none. VIR (id=1) only has its label because backfilled via SQL UPDATE 2026-04-25; CC (id=3) backfilled the same way 2026-04-30. **Operator workflow tax:** every hypothesis-tagged trade taken via the web form requires a SQL UPDATE backfill to attribute it correctly. Bearable at current ~50-trades/year ceiling, but real friction. **Fix scope:** small-medium dispatch (~3-5 tasks): (a) add `hypothesis_label` field to `TradeEntryFormVM` populated via the same matcher logic the CLI uses (`_lookup_active_recommendation_label` from `swing.web.view_models.dashboard` already exists; matches the cross-import note); (b) add hidden input + read-only display rows in `partials/trade_entry_form.html.j2` (mirrors the sector/industry pattern from sector capture Phase 1); (c) add `Form(...)` param + thread through `EntryRequest.hypothesis_label` in `swing/web/routes/trades.py entry_post`; (d) discriminating tests + soft-warn round-trip preserves the label (per the multi-path-ingestion lesson 2026-04-29). **Sequencing:** sequence after Phase 4 cleanup-remainder ships (operator-paced; not Phase-4-blocking). OR inline into Phase 4 if implementer has bandwidth — but operator decided Phase 4 plan continues separately, so default to standalone follow-up dispatch post-Phase-4. **Cross-references:** orchestrator-context.md "Recent decisions and framings" 2026-04-25 (hypothesis-recommendation engine framing — "dashboard PROPOSES, operator DISPOSES"); 2026-04-25 "Prefix-label convention" (operator-facing — manual labels start with canonical hypothesis name); CLI precedent at `swing/cli.py:486-501` (pre-fill logic to mirror in web).

- **(2026-04-30 entry-form stop-value observation; defer-investigate)** Operator reported during CC entry (Take-this-trade button on hyp-recs expansion, 2026-04-30): "the table did not have the stop values correctly populated; potentially others." Operator instruction: "we do not need to investigate further" until another instance reproduces. Logged for memory; if a second observation surfaces with screenshots or specific field values, dispatch investigation-first. **Possible mechanisms (NON-exhaustive; do NOT design fixes against these without empirical reproduction):** (a) sell-stop snapshot field reads from the wrong source (Candidate.initial_stop vs SizingResult.stop_loss vs computed-fallback); (b) origin-aware re-resolution at form-render time loses snapshot context; (c) PriceFetcher stale archive returning wrong reference price (Phase 3 just shipped; not yet operator-verified end-to-end); (d) ToCToU window between expansion-render and form-render. **No action until reproducer.**

---

## 2026-04-26 chart-pattern flag-v1 brainstorm follow-ups

Items surfaced during the chart-pattern flag-v1 brainstorm dispatch (commit chain `9583f19..081f689`, spec at `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`, 5 adversarial Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`). Implementation queued via writing-plans dispatch; these items are explicitly out of V1 scope.

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

## 2026-04-26 chart-pattern flag-v1 Phase 1 → Phase 2 handoff items

Items surfaced by Phase 1 execution (commit chain `dffb723..574869f`, 4 adversarial Codex rounds → `NO_NEW_CRITICAL_MAJOR`) that are deferred to Phase 2 or later phases per scope discipline.

### For Phase 2 (persistence layer) implementer:

- **`components_json` schema design point.** Phase 1's `_evaluate_candidate` returns 11 raw measurements (`pole_M, flag_N, pole_gain, pullback_depth, tightness_ratio, volume_ratio, ma_structure, flag_floor_holds, pole_high, flag_low, pivot`). Spec §3.1.1 lists additional EXAMPLE keys (`pole_gain_clearance`, `pullback_clearance`, `tightness_clearance`, `volume_clearance`, `sma10_at_flag_start`, `sma20_at_flag_start`, `sma50_at_flag_start`) that are NOT currently populated. **Phase 2 design decision:** extend Phase 1's `_evaluate_candidate` to also populate clearances + SMAs (cheap — already computed inside helpers), so `components_json` carries them. **Recommendation: extend** — SMA values become unrecoverable once raw bars aren't persisted alongside, and clearances enable retroactive analysis of why a classification fell where it did.
- **Tightness test naming convention.** `test_tightness_ratio_gate_above/below_threshold_*` are detection-outcome regression tests at search-path-dependent boundaries, NOT direct gate-threshold tests. The actual gate-correctness verification is `test_tightness_ratio_gate_is_threshold_sensitive` (cfg-injection). Phase 2-7 detection-outcome regression tests should follow the same naming pattern.
- **Pure-function discipline verified for Phase 1.** `classify_flag(bars)` does NOT mutate the input DataFrame. Phase 3 can safely reuse the same `bars` object for both `render_chart` and `classify_flag` without copy-on-write concerns.
- **Classifier-error path adapter is Phase 3 territory.** Phase 1 Task 1.13 only verifies the type contract (`pattern: str | None`). The actual exception-catching adapter that constructs `FlagClassificationResult(pattern=None, components={"error": ...})` lives in `_step_charts` per spec §3.3 — Phase 3 implements it. Phase 1 classifier itself does NOT catch.
- **`pre_run_bars=50` in `tests/evaluation/patterns/_synthetic.py`.** Required to satisfy gate 5's 55-bar SMA50 lookback floor. Documented inline. Future fixture refactors must preserve `pre_run_bars + pole_bars >= 55`.

### For Phase 5 (trade-entry form + CLI) — performance budget:

- **Classifier hot loop performance.** `_evaluate_candidate` is invoked ~442× per `classify_flag` call; final reviewer measured ~44-49ms per call on a 250-bar DataFrame, ~700ms for a 15-ticker batch. Spec budgets sub-millisecond with 10× tolerance (10ms target). Single-digit-ms is achievable by hoisting the four `bars[col].to_numpy(dtype=float)` conversions out of the inner loop (they are invariant across all (M, N) candidates). **Phase 5 should measure end-to-end pipeline overhead with the live classifier active across 15 chart-scope tickers and tune if total overhead exceeds 1.5s.** Optimization is straightforward and won't change behavior.

### Spec cleanups landed in this housekeeping commit:

- **Spec §3.1.2 step 4 vestigial sentence removed.** Phase 1 implementer (Q1, 2026-04-26) flagged that "When no candidate passes any gate, the (M=5, N=5) pair's measurements are persisted as a deterministic baseline" was structurally unreachable under MIN_BARS=36 (every candidate has data_window passing, so the no-gate-passes condition is impossible). Removed; precise definition now stands alone. Phase 2 implementer should NOT design persistence around the (5,5) fallback case.
- **(M=5, N=5) literal fallback in `swing/evaluation/patterns/flag_classifier.py`.** Retained but unreachable; documented inline. If Phase 7 ever lowers `MIN_BARS`, this branch activates and would benefit from actual (5,5) measurements being computed and returned (current branch returns only `{"pole_M": 5.0, "flag_N": 5.0}`). Surface for spec follow-up if MIN_BARS is ever lowered.

---

## 2026-04-26 chart-pattern flag-v1 Phase 2 → Phase 3 handoff items

Items surfaced by Phase 2 execution (commit chain `8eca791..158efd2` + retro `3d6e03d`, 2 adversarial Codex rounds → `NO_NEW_CRITICAL_MAJOR`) that are deferred to Phase 3 or are housekeeping items.

### For Phase 3 (pipeline integration) implementer:

- **`_step_charts` wiring is the Phase 3 main work.** Both `classify_flag(ohlcv.tail(60))` and `insert_classification(conn, pipeline_run_id=run.id, ticker=t, result=classification, computed_at=...)` call signatures are stable and tested as of Phase 2. Phase 3 wires them into `_step_charts` per-ticker loop; persists classification row in same `lease.fenced_write()` block as the chart_target update.
- **`_serialize_components` handles NaN sanitization at the persistence boundary** (added in Phase 2 commit `115c96b` as Codex R1 Major 2 fix). Phase 3 can pass any `FlagClassificationResult.components` dict (including those from `_enrich_components` with NaN SMAs) without pre-processing — the repo's `insert_classification` handles it.
- **Per spec §3.3 lines 396-401, classifier-error rows MUST be constructed with `components={"error": repr(exc)}`.** The repo does NOT enforce this contract (Codex R1 Minor 1 ACCEPTED rationale: V1 trust model — _step_charts is sole producer; spec §3.3 prescribes the construction; centralizing as repo-layer enforcement is V2 hardening). **Phase 3's `_step_charts` exception handler is the sole owner of that invariant.**
- **`render_chart` `pattern_overlay` kwarg as no-op for Phase 3.** Per the plan, Phase 3 adds the `pattern_overlay: PatternOverlay | None = None` kwarg to `render_chart` but does NOT paint the overlay yet. The actual painting is Phase 6. Phase 3's render_chart change is API-surface-only.

### For Phase 5 (trade-entry form + CLI):

- **Repo-layer cross-column invariant covers ALL spec §3.2.2 joint-NULL invariants now** (Codex R1 Major 1 closure in commit `115c96b`). Phase 5's `record_entry` inherits this guarantee — any invalid combination of (algo, confidence, operator, anchor) at insert time raises `ValueError`.
- **Trade dataclass's 4 chart_pattern fields default to None.** Phase 5's entry form / record_entry will populate them from the cached classification + operator override; the cross-column invariant rejects invalid combinations at insert time (4 invariants enforced).

### Housekeeping items:

- **`tests/data/test_db_v8.py` filename now stale** (schema is v10 after Phase 2 migrations 0009 + 0010). Final code reviewer flagged as Minor — recommend rename to `test_schema_version_pin.py` in a future housekeeping batch.
- **Several scratch directories from Phase 2 parallel-subagent pytest runs remain in repo root.** `.pytest-tmp/`, `.tmp/`, `.tmp-pytest/`, `.tmp_pytest_red/`, `.tmp_pytest_red_run/`, `ptemp/`, `pytest_temp_red/`, `task28_pytest_green/`, `task28_pytest_green2/`, `task28_pytest_tmp/` (10+ directories). Gitignored at runtime (don't show in `git status`) but pollute the working directory. Cleanup in a housekeeping pass.
- **Phase 2 dispatch brief was lost.** Orchestrator drafted `docs/phase3e-chart-pattern-phase2-execution-brief.md` in the orchestrator-thread and left it untracked, expecting the dispatch chain to commit it (as happened with Phase 1's `9f0a778`). Some operation during Phase 2 execution (likely a subagent's working-tree cleanup) deleted the untracked file; brief is not in working tree, not in git history. Lesson captured in orchestrator-context: **commit briefs immediately after writing them; don't rely on the dispatch chain.**

### Process-meta items:

- **Phase 2 surfaced subagent-collision pattern in `subagent-driven-development`.** See orchestrator-context "Lessons captured" entry on `copowers:executing-plans` self-collision. Phase 3 brief addresses this with explicit disjoint-task-partitioning discipline; worktree isolation is the fallback if collision recurs. **If Phase 3 collides again despite the partitioning discipline, escalate to worktree isolation in Phase 4+.**

---

## 2026-04-26 chart-pattern flag-v1 Phase 3 → Phase 4 handoff items

Items surfaced by Phase 3 execution (commit chain `6ac8f56..dd699de` including `b080da9`+`132142c` rogue/revert pair, 4 adversarial Codex rounds → `NO_NEW_CRITICAL_MAJOR`) that are deferred to Phase 4 or are housekeeping items.

### For Phase 4 (watchlist + dashboard read paths) implementer:

- **Task 4.0a — date deserialization fix (Phase 2 carve-out extension; Phase 4 prerequisite).** Codex Phase 3 R3 Major 1 surfaced that `_row_to_classification` returns ISO date strings instead of `date` objects despite the `PipelinePatternClassification` dataclass annotation being `date | None`. Phase 3 was scope-locked OUT of `swing/data/` so the fix was deferred. Phase 4 brief MUST include Task 4.0a as the first task: `date.fromisoformat(row[N])` for the four anchor columns (`pole_start_date`, `pole_end_date`, `flag_start_date`, `flag_end_date`) in `_row_to_classification` AND the analogous parsing in `list_classifications_for_run`'s row mapping. Without this fix, Phase 4's watchlist VM consumption of `cls.pole_start_date` etc. will be ISO strings at runtime; Phase 6 chart overlay painting will trip on the same. Small fix (~5 lines); justified Phase 2 carve-out extension.
- **`_step_charts` per-ticker fenced_write granularity preserved.** Each ticker outcome is its own `lease.fenced_write()` transaction (~15 small transactions per pipeline run for chart-scope tickers). Phase 3 just bundled the classification INSERT into the same transaction as the chart_target update; existing pattern unchanged. If Phase 4+ ever needs end-of-step batching for performance, the existing fenced_write granularity supports refactoring; Phase 3 didn't change it.
- **End-of-step summary log line `flag_classifier: {success}/{attempts} ok, {errors} errors`** is now the operator-facing visibility surface for classifier health per pipeline run. Phase 4's "dashboard banner for classifier-error count" (V2 deferred per spec §3.3) consumes the same counters; if/when that ships, the banner can pull from this log line OR re-aggregate from `pipeline_pattern_classifications` rows where `pattern IS NULL AND components_json LIKE '%"error":%'`.
- **`PatternOverlay.from_classification(r)` filtering rule.** Returns None when `not r.detected or r.pattern != 'flag'`. The `r.pattern != 'flag'` check covers both `'none'` and None (classifier-error rows). Phase 6 painting won't fire on classifier-error rows — matches spec §3.4 design.
- **Test-suite baseline for Phase 4: 1059 fast tests** passing on main at HEAD `dd699de`. Phase 4 can add tests for `WatchlistVM.pattern_tags` field, `_pattern_tags` helper, watchlist template flag-tag rendering, and the sort-neutrality regression test without disturbing Phase 3's 7 new tests.

### For Phase 6 (chart overlay painting):

- **Byte-identity tests will FAIL when Phase 6 lands.** Phase 3 added `test_render_chart_pattern_overlay_none_is_byte_identical_to_default` and `test_render_chart_real_pattern_overlay_is_byte_identical_to_default` to enforce the no-op contract. These tests are LOAD-BEARING for Phase 3's no-op stub design — when Phase 6 implements actual band-painting + algo-pivot annotation, the byte-identity will break. Phase 6 implementer should expect to update or remove these tests as part of the painting work (replace with overlay-rendered equivalence tests).

### Housekeeping items:

- **`tests/data/test_db_v8.py` filename now stale** (schema is v10 after Phase 2 migrations 0009 + 0010). Recommended rename to `test_schema_version_pin.py`. Carry-over from Phase 2 → Phase 3 handoff; still pending.
- **Scratch directories accumulating in repo root.** Phase 2 left 10+ (`.tmp_pytest_red/`, `task28_pytest_*/`, etc.); Phase 3 added 4 more (`.tmp-pytest-phase3-task32/`, `tmp-pytest-phase3/`, `tmp-pytest-phase3-task32/`, `tmp-task32-probe/`). All blocked by Windows ACL on `Remove-Item`. Aggregate cleanup is a privileged-tool task (`takeown` + `icacls`) — defer until convenient or escalate as a separate operator-action item.
- **Phase 2 dispatch brief recovered.** Earlier housekeeping commit `3912ba9` noted the brief was "lost"; post-Phase-3 verification confirmed the file was on disk the whole time (`ls` returned "No such file" due to transient Windows ACL state). Brief committed to repo in this housekeeping batch. Lesson refined in orchestrator-context: untracked files in working tree are vulnerable to TRANSIENT inaccessibility (ACL state, subagent activity, IDE indexing) — the principle of "commit briefs immediately" stands regardless of the specific failure mode.

### Process-meta items:

- **Phase 3 produced one rogue task duplicate** (`b080da9` + revert `132142c`) despite single-subagent dispatch. Bounded noise (~20% of chain vs Phase 2's ~30%); net code state correct; Codex caught it. Operator decision: continue with brief discipline + ADD observable verification (subagent must include `git log --grep="Task X.Y" --oneline` output in commit body before each task commit) for Phase 4. If Phase 4 sees another rogue, escalate to worktree isolation in Phase 5+.
- **Review-fix commit message convention formalized** in orchestrator-context "Binding conventions" section (2026-04-26). Task implementations get task IDs; review-fix commits use round + finding ID format; format-only cleanup commits no task ID needed.

---

## 2026-04-26 chart-pattern flag-v1 Phase 4 → Phase 5 handoff items

Items surfaced by Phase 4 execution (commit chain `195acbc..ad29f9e`, 3 adversarial Codex rounds → `NO_NEW_CRITICAL_MAJOR`, 13 commits, 1059→1102 fast tests +43, ZERO rogue duplicate task commits) that are deferred to Phase 5 or are housekeeping items.

### For Phase 5 (trade-entry form + CLI) implementer:

- **Task 5.0a — `PipelinePatternClassification` dataclass annotation retype (Phase 2 carve-out extension; Phase 5 prerequisite).** Phase 4 Task 4.0a fixed `_row_to_classification` to parse anchor dates as `date` objects at runtime, but the dataclass annotation in `swing/data/models.py:274` still says `str | None`. Type-vs-runtime drift. Phase 5's `build_entry_form_vm` and Phase 6's chart overlay painting both `isinstance(cls.pole_start_date, date)` checks; the annotation should match runtime. Small fix (~4 line annotations); justified Phase 2 carve-out extension; mirrors Phase 4's Task 4.0a pattern (standalone first commit before Phase 5 main work).
- **`pipeline_run_id` resolution pattern.** Phase 5's `build_entry_form_vm` should mirror Phase 4's single-round-trip `SELECT id, evaluation_run_id FROM pipeline_runs WHERE state='complete' ORDER BY finished_ts DESC LIMIT 1` query (avoids the secondary `WHERE evaluation_run_id = ?` lookup which races with concurrent pipeline_runs writes). The `id` IS the parent `pipeline_run_id` by construction.
- **`_pattern_tags` is SIBLING to `_flag_tags`.** Phase 5's per-row resolution for the entry-form Chart-Pattern section uses `_pattern_tags`-style filtering logic if it needs to gate display, NOT touch `_flag_tags`. The `pattern_tags` parallel VM field design is the architectural pattern.
- **Snapshot-at-entry-surface ToCToU pattern (per spec §3.6 + Phase 1 brainstorm Decision 6).** `EntryRequest` carries the resolved snapshot + `pipeline_run_id` audit anchor; `record_entry` persists what's passed AS-IS (no re-resolve at submit). Cache resolution happens ONCE at entry-surface (form/CLI) per the spec ToCToU fix.
- **CLI cached-only refusal gate.** `swing trade entry --chart-pattern-operator` mirrors form's stub gate — refuses for tickers without cached classification (per locked-constraint #5; per spec §3.6 + Phase 1 Codex R1 C1 fix). Symmetric refusal across entry surfaces.
- **Operator override surface (per spec §3.6).** Dropdown {Accept algo / flag / none / other(text)}; default = Accept algo → NULL persisted. Free-text "other" path canonicalized like `hypothesis_label` (NFC + control-byte stripping; reuse the existing canonicalization helper).
- **Repo-layer cross-column invariant** (4 cases enforced in Phase 2). Phase 5's `record_entry` inherits this guarantee — any invalid combination of (algo, confidence, operator, anchor) at insert time raises `ValueError`.
- **Shared seed helper at `tests/web/test_view_models/_pattern_classification_seed.py`** (leading-underscore opts out of pytest collection). Phase 5/6/7 tests can reuse `seed_pipeline_with_classification`, `add_active_watchlist_row`, `delete_all_classifications` rather than rebuilding seed scaffolding.
- **`build_watchlist_row` reuses run-wide classification fetch** (Phase 4 R1 Minor 1 accepted): single-source threshold + format. Trigger threshold for optimization is watchlist > ~100 rows. Phase 5 trade-entry form's per-ticker fetch may want to use `get_classification(pipeline_run_id, ticker)` directly for lighter rendering, but Phase 4's pattern is fine for current scale.
- **Test-suite baseline for Phase 5: 1102 fast tests** passing on main at HEAD `ad29f9e`. Phase 5 can add tests for `TradeEntryFormVM.chart_pattern_*` fields, `EntryRequest.chart_pattern_*` fields, `record_entry` snapshot persistence, CLI flag refusal gate, and operator-override canonicalization.

### Brief discipline updates for Phase 5:

- **Observable verification refined to subject-only anchored grep** (operator decision 2026-04-26): `git log --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'`. Eliminates forward-reference false positives that surfaced in Phase 4 (commit bodies cross-referencing future task IDs in narrative prose). Phase 5 brief adopts this refinement.
- **Don't blanket-require 5-VM rule.** CLAUDE.md base-layout VM gotcha applies only when `base.html.j2` dereferences the field. Phase 5's new `chart_pattern_*` fields on `TradeEntryFormVM` are consumer-scoped (entry form only); `base.html.j2` doesn't reference them. Don't blanket-require all 5 base-layout VMs to gain the field.
- **Downstream-test scope acceptance.** When the brief authorizes Task 5.0a Phase 2 carve-out extension (annotation retype touching `swing/data/models.py`), downstream tests of the modified file are naturally in-scope. Brief should explicitly say "downstream tests of carve-out file are in-scope by extension" to pre-empt scope-deviation findings.

### Housekeeping items:

- **Scratch directories accumulating across phases.** Phase 2 left 10+ (`.tmp_pytest_red/`, `task28_pytest_*/`, etc.); Phase 3 added 4 more (`.tmp-pytest-phase3-task32/`, `tmp-pytest-phase3/`, `tmp-pytest-phase3-task32/`, `tmp-task32-probe/`); Phase 4 cleaned its own (`.tmp-phase4/`) but inherited the prior pile remains. All blocked by Windows ACL on `Remove-Item`. Aggregate cleanup is a privileged-tool task (`takeown` + `icacls`) — defer until convenient or escalate as a separate operator-action item.
- **`tests/data/test_db_v8.py` filename now stale** (schema is v10 after Phase 2 migrations 0009 + 0010). Recommended rename to `test_schema_version_pin.py`. Carry-over from Phase 2/3 handoffs; still pending.

### Process-meta items:

- **Phase 4 vindicated single-subagent + observable-verification approach.** ZERO rogue duplicates this phase (vs Phase 3's one and Phase 2's many). Brief discipline + observable evidence is a working alternative to worktree isolation at this scale. Worktree isolation reserved as fallback for future phases if a new failure mode emerges.
- **Codex's adversarial review pattern across 4 phases:** R1 catches structural issues (Phase 1: cfg-injection sensitivity needed; Phase 2: orphan-confidence guard, NaN strict-JSON; Phase 3: log denominator semantics; Phase 4: compounding-confound conflation), R2 catches subtle vacuousness (Phase 4: ticker-symmetry vacuousness), R3+ refine. The 5-round investment is yielding repeated ROI on test-quality dimension; not just spec-fidelity. Worth continuing.

---

## 2026-04-26 chart-pattern flag-v1 Phase 5 → Phase 6 handoff items

Items surfaced by Phase 5 execution (commit chain `9b7908c..27fb060`, 13 commits incl Task 5.0a + 4 review-fixes + 2 post-report R2-minor follow-ups, 2 adversarial Codex rounds → `NO_NEW_CRITICAL_MAJOR`, 1102→1124 fast tests +22, ZERO rogue duplicate task commits) that are deferred to Phase 6 or are housekeeping items.

### For Phase 6 (chart overlay painting) implementer:

- **Phase 6 lights up the chart-overlay painting (no-op stub from Phase 3).** Phase 3 added `pattern_overlay: PatternOverlay | None = None` kwarg to `render_chart` as a no-op stub; Phase 6 implements actual `fill_betweenx` pole/flag bands + algo-pivot horizontal segment + title annotation per spec §3.4. Existing candidate-pivot hline preserved as a separate visual element (algo-pivot is distinct).
- **Phase 3 byte-identity tests WILL FAIL when Phase 6 lands** (`test_render_chart_pattern_overlay_none_is_byte_identical_to_default` + `test_render_chart_real_pattern_overlay_is_byte_identical_to_default` were load-bearing for Phase 3's no-op contract). Phase 6 implementer should expect to UPDATE or REPLACE these with overlay-rendered equivalence tests (e.g., LineCollection count delta from baseline; pole/flag band fill_betweenx presence; title annotation contains classification label).
- **`PatternOverlay.from_classification(r)` filtering rule already in place** (Phase 3): returns None when `not r.detected or r.pattern != 'flag'`. Covers classifier-error rows (`pattern=NULL`) implicitly. No Phase 6 changes needed there.
- **Phase 5 Task 5.0a aligned the dataclass annotation with Phase 4 runtime fix.** Phase 6 painting can `isinstance(cls.pole_start_date, date)` and use `pd.Timestamp(cls.pole_start_date)` directly without TypeError on `str.isoformat()`.
- **Test-suite baseline for Phase 6: 1124 fast tests** passing on main at HEAD `27fb060`.
- **Spec language fidelity** (per 2026-04-26 lesson on `axvspan` vs `fill_betweenx`): spec explicitly specifies `fill_betweenx` for the band painting. Use the spec's API name verbatim even if alternatives are more familiar.

### Brief discipline updates for Phase 6:

- **Continue subject-only grep observable verification** (Phase 4 + Phase 5 both ZERO rogues with this pattern): `git log --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'` in commit body before each task implementation commit.
- **Continue 3-tier commit-message convention** (refined Phase 5): task implementations (`feat(area): Task X.Y — ...`); review-fix commits including internal code-review (`fix(area): code-review I1 — ...`) AND Codex (`fix(area): Codex R1 Major 2 — ...`); format-only cleanup (no task ID).
- **Encourage internal code-review BEFORE Codex round.** Per Phase 5 lesson: pre-empts plan-anticipated misses; saves Codex round budget. Brief should explicitly suggest the internal pass after task implementations land but before invoking Codex.
- **Don't blanket-require base-layout 5-VM rule.** Phase 6 touches `swing/rendering/`; doesn't add VM fields. Not applicable.
- **In-scope-by-extension clause** (per Phase 4 + Phase 5 pattern): Phase 6 implicitly authorizes downstream tests of `render_chart` to be updated/replaced (the byte-identity tests from Phase 3 are the obvious case). Brief should explicitly say "Phase 3's byte-identity tests are expected to fail and need to be replaced with overlay-rendered equivalence tests" to pre-empt scope-deviation findings.

### Housekeeping items:

- **Scratch directories accumulating across phases.** Phase 2 left 10+ (`.tmp_pytest_red/`, `task28_pytest_*/`, etc.); Phase 3 added 4 more (`.tmp-pytest-phase3-task32/`, `tmp-pytest-phase3/`, `tmp-pytest-phase3-task32/`, `tmp-task32-probe/`); Phase 4 cleaned its own (`.tmp-phase4/`); Phase 5 cleaned its own (`.tmp-phase5/`); inherited Phase 2-3 pile remains. All blocked by Windows ACL on `Remove-Item`. Aggregate cleanup is a privileged-tool task (`takeown` + `icacls`) — defer until convenient or escalate as a separate operator-action item.
- **`tests/data/test_db_v8.py` filename now stale** (schema is v10 after Phase 2 migrations 0009 + 0010). Recommended rename to `test_schema_version_pin.py`. Carry-over from Phase 2/3/4 handoffs; still pending.

### Process-meta items:

- **Phase 4 + Phase 5 vindicated single-subagent + observable-verification approach.** ZERO rogue duplicates across both phases (vs Phase 3's one and Phase 2's many). Brief discipline + observable evidence + subject-only grep refinement is a working alternative to worktree isolation at this scale. Worktree isolation reserved as fallback for novel failure modes.
- **Codex's 5-phase review pattern shows compound ROI:** R1 catches structural issues; R2 catches subtle vacuousness; R3+ refine; Phase 5 added a NEW class — cross-feature interactions (R1 M2 soft-warn × new chart_pattern fields) that internal review naturally misses. The 5-round investment yields repeated ROI on test-quality + spec-fidelity + cross-feature-integration dimensions.
- **R2 minors closed post-report.** Phase 5 R2 minors (schema-message coupling docs; soft-warn × "other" test) were ACCEPTED with rationale in implementer's return report; commits `4ef9044` + `27fb060` landed post-report addressing them. Net: nothing deferred; Phase 5 → Phase 6 handoff doesn't carry R2-minor advisory follow-ups.

---

## 2026-04-26 chart-pattern flag-v1 Phase 6 → Phase 7 handoff items

Items surfaced by Phase 6 execution (commit chain `bce79b1..13d8cc5` + mathtext follow-up `2fd0ecc`, 7+1 commits, 4 adversarial Codex rounds → `NO_NEW_CRITICAL_MAJOR`, 1124→1127 fast tests +3, ZERO rogue duplicate task commits) plus Q1 + Q2 operator decisions.

### For Phase 7 (operator-labeled fixtures + integration tests + tuning) implementer:

**Phase 7 implementer-side scope is small.** Tasks 7.1 (fixture directory + labeling protocol README) + 7.2 (fixture-loader + parametrized integration test) + 7.4 checkpoint (gated on operator-labeling + tuning). Task 7.3 (≥15 fixtures labeled by operator) is OPERATOR-ONLY work running in parallel with implementer's 7.1/7.2 ship.

- **Phase 7 brief should ship 7.1 + 7.2 immediately.** Task 7.3 operator-labeling can run at any pace alongside; Task 7.4 closes after operator labeling + FP-biased tuning.
- **Chart overlay painting works on in-window portions of any classification's date range.** Phase 6 documented and tested LEFT-truncation (date before chart window snaps to index 0) and RIGHT-truncation (date after last bar — zero-width band at right edge) as intentional. No new edge cases expected from Phase 7 fixture parametrization.
- **Test-suite baseline for Phase 7: 1127 fast tests** passing on main at HEAD `2fd0ecc` (post-mathtext-fix).
- **Two-pivot rendering preserved** per spec §3.4. Operator-labeling work in Task 7.3 will see both candidate-pivot (full-width hline) AND algo-pivot (flag-region segment); they may coincide or differ. Spec deliberately allows visual comparison.
- **Mathtext quirk fixed** (commit `2fd0ecc`). Chart titles now render legibly without mathtext italicization.
- **Manual verification procedure prepared** at `docs/chart-pattern-flag-v1-manual-verification.md`. Operator walks through web + CLI surfaces post Phase 7 implementer ship to confirm everything displays correctly. Procedure will likely surface follow-up items.

### Brief discipline updates for Phase 7:

- **Continue subject-only grep observable verification** (3-phase ZERO-rogue track record: Phases 4 + 5 + 6).
- **Continue 3-tier (now 4-tier with `(internal)` qualifier) commit-message convention.** Internal-Codex commits append `(internal)` qualifier per Q2 decision (2026-04-26 post-Phase-6 triage); orchestrator-Codex commits stay as-is.
- **Encourage internal review BEFORE Codex** at BOTH discipline levels: manual code-review (per Phase 5 lesson) AND internal-Codex round (per Phase 6 lesson). Each layer pre-empts orchestrator round budget.
- **Subagent role-partitioning within a task is collision-safe.** Phase 6 dispatched 7 subagents at different roles within Task 6.1 (implementer / reviewer / fix-implementer) with ZERO rogues. The disjoint-task-partitioning discipline operates at the TASK level, not subagent-count level.
- **Manual visual verification is required for rendering changes.** If Phase 7 fixture parametrization touches chart rendering (e.g., overlay edge cases per the LEFT/RIGHT truncation), manual PNG inspection must accompany structural test verification.

### Housekeeping items:

- **Scratch directories accumulating across phases.** Phase 2: 10+; Phase 3: 4 more; Phase 4: cleaned own; Phase 5: cleaned own; Phase 6: created `.tmp-phase6-*` and similar (ACL-blocked). All blocked by Windows ACL on `Remove-Item`. Aggregate cleanup is a privileged-tool task (`takeown` + `icacls`) — defer until convenient or escalate as a separate operator-action item.
- **`tests/data/test_db_v8.py` filename now stale** (schema is v10). Recommended rename to `test_schema_version_pin.py`. Carry-over from Phase 2-5 handoffs; still pending.

### Process-meta items:

- **Phase 4 + Phase 5 + Phase 6 all produced ZERO rogue duplicate task commits.** Single-subagent + observable verification + subject-only grep refinement is robust at this project's scale. Worktree isolation reserved as fallback for novel failure modes only.
- **Codex's 6-phase review pattern shows compound ROI:** R1 catches structural issues; R2 catches subtle vacuousness; R3+ refine + escalate coupling concerns into explicit contracts; Phase 5 added cross-feature interactions (soft-warn × new fields); Phase 6 added internal-Codex pre-emption. The 5-round investment yields repeated ROI on test-quality + spec-fidelity + cross-feature-integration + visual-correctness + contract-documentation dimensions.
- **Phase 6 commit-message convention surfaced 4th case:** internal-Codex within-task vs orchestrator-Codex post-task. `(internal)` qualifier formalized in Binding conventions for Phase 7+.

---

## 2026-04-27 chart-pattern flag-v1 Phase 7 implementer-side → operator + orchestrator handoff

Phase 7 implementer-side complete (commit chain `528d38b..ca66216`, 11 commits, 5 adversarial Codex rounds → `NO_NEW_CRITICAL_MAJOR`, 1127→1145 fast tests +18 plus +1 gracefully-skipped integration test, 8 subagent dispatches with ZERO rogue duplicate task commits). Operator-labeling boundary preserved end-to-end.

### For OPERATOR — manual verification + Task 7.3 fixture labeling:

**Step 1: Manual verification walkthrough.** Run `docs/chart-pattern-flag-v1-manual-verification.md` end-to-end (~30-45 min thorough; ~10-15 min spot-check). Surfaces any UI bugs in chart-pattern surfaces (dashboard, /watchlist, chart overlay, trade-entry form, CLI) before fixture labeling work begins. Any check failures → surface to orchestrator before proceeding.

**Step 2: Task 7.3 fixture labeling (operator pace).** Per spec §4.2 + Phase 7 implementer's labeling protocol README at `tests/evaluation/patterns/fixtures/README.md`:
- ≥15 fixtures floor = 8 flags + 7 non-flags spanning rejection cases (wide-and-loose, deep base/cup, sideways drift with no pole, late-stage failed breakout, stage-4 with bounce, multi-month flat base, ambiguous edge case).
- File format: paired `<TICKER>_<YYYY-MM-DD>_<label>.csv` (literal yfinance pull) + `.json` (label + notes + optional expected_confidence_min).
- Loader canonicalization: yfinance pull is preserved on disk; helper trims to last 60 bars before classification. Operator's visual labeling should focus on the right edge of the chart.
- JSON schema validation gates (per Codex R1 M2 + R2 M2): label ∈ {flag, none}; notes is required (no silent default); expected_confidence_min must be numeric in [0,1] AND only set on flag fixtures (not none).
- Fixtures immutable: never edit-in-place; retire-and-replace if a label changes.
- Generation procedure example in README §6: `python -c "import yfinance as yf; df = yf.Ticker('TICKER').history(end='YYYY-MM-DD', period='90d'); df.to_csv('tests/evaluation/patterns/fixtures/TICKER_YYYY-MM-DD_flag.csv')"` (or use period='120d' if a holiday-heavy month yields <60 trading days).
- MIN_BARS in classifier is 36; spec's 60-bar contract is more conservative. period='90d' is sufficient for typical months.

**Step 3: Each fixture commit:** `test(patterns): add labeled flag fixture <TICKER>_<DATE>` (or `none` variant). Standard convention; not a "task implementation" so no task-ID prefix needed.

### For ORCHESTRATOR — Task 7.4 checkpoint (gated on operator labeling):

**When Task 7.3 fixtures ship (≥15 committed):**

1. Run `python -m pytest tests/evaluation/patterns/test_flag_classifier_integration.py -v` to execute parametrized integration tests over committed fixtures.
2. Each parametrized test reports `<fixture-name> PASSED/FAILED`; failed assertions include label + actual pattern + notes in the error message.
3. **Operator manually classifies failures as FP (algo says flag, operator labeled none) or FN (algo says none, operator labeled flag).** Per Q2 (2026-04-27): no automated FP/FN aggregator was added in V1; operator does manual classification from pytest output. Acceptable for V1 personal-use scope; if operator needs aggregation tooling, add as a small standalone follow-up.
4. **Tune `cfg.classifier.*` if FP > FN per spec §3.1.4.** FP-biased: prefer false-negatives (algo missing real flags) over false-positives (algo flagging non-flags) — operator's eye is the validating ground truth, so over-flagging wastes operator-review time. Tighten thresholds (raise `flag_pole_gain_min`, lower `flag_pullback_depth_max`, etc.) until FP ≤ FN at default thresholds OR operator accepts the current calibration.
5. **Phase 7 checkpoint criteria:** ≥15 fixtures committed; integration tests run; FP/FN classified; tuning applied (if needed) OR baseline accepted; final test-suite run green.
6. **V1 ship criteria:** Task 7.4 closure marks chart-pattern flag-v1 V1 fully shipped. Document outcome in orchestrator-context "Recent decisions and framings" + lessons captured.

### V1 known limitations (deferred to V2+):

- Manual-trade fallback for out-of-chart-scope tickers (locked-constraint #5; spec §3.6).
- ML / LLM / hybrid classifiers (operator preference: rule-based geometric for V1).
- Multi-timeframe analysis (weekly + daily); currently daily-only.
- Real-time / intraday classification.
- Sort-PARTICIPATING flag tag (sort-neutral in V1 by spec).
- Calibration study (algo vs operator agreement-rate); gated on 20+ overrides.
- Slow-test live-fetch suite (deferred per spec §4.3).
- Tuning-history versioning.
- Schema-layer cross-column constraint hardening on `trades` (CREATE-COPY-DROP-RENAME).
- Hidden form-field tampering hardening (re-resolve at submit + validate).
- Dashboard banner for classifier-error count.
- Additional patterns beyond `flag_pattern` (V1 = single pattern; V2+ extensions via separate dispatch).
- `(M=5, N=5)` literal fallback in classifier (unreachable under MIN_BARS=36; documented inline).
- Automated FP/FN aggregator for Task 7.4 tuning (Q2, 2026-04-27).

### Process-meta items (post-V1):

- **4-phase ZERO-rogue track record (Phases 4 + 5 + 6 + 7).** Single-subagent dispatch + observable verification + 4-tier commit-message convention is the working baseline at this project's scale. Worktree isolation NOT escalated.
- **Codex's 7-phase review pattern shows compound ROI:** R1 catches structural; R2 catches second-order interactions; R3+ catches defense-in-depth; Phase 7 added induced-bug pattern (R3→R4 chain). The 5-round investment yields repeated ROI on test-quality + spec-fidelity + cross-feature-integration + visual-correctness + contract-documentation + induced-bug-detection dimensions.
- **Subject-only grep regex amended to ERE + POSIX** (Q1, 2026-04-27). Past briefs' BRE-incompatible regex was technically non-functional; the discipline still worked because of other partitioning rules. Phase 7+ briefs use the ERE form.

---

## 2026-04-27 chart-pattern flag-v1 manual verification round 1 — findings

Full technical detail in `docs/chart-pattern-flag-v1-manual-verification-results.md`. Summary of action items by tier:

### Tier 1 — V1-quality fix (dispatch BEFORE Task 7.3 fixture labeling)

1. **Mathtext title regression** — commit `2fd0ecc` `\$` escape doesn't prevent matplotlib mathtext entry; rendered title shows `pivot 72.97stop40.69` with "stop" italicized. Fix options: (a) remove `$` from title format, (b) `fig.suptitle(..., parse_math=False)` after `mpf.plot(returnfig=True)`. Recommended: (a) for simplicity. Files: `swing/rendering/charts.py:86`, `tests/rendering/test_chart_overlay.py:270` and `:287`. **Manual visual verification required** before committing — do NOT rely on string-equality tests alone (the lesson from this regression).

### Tier 2 — Operator-workflow improvements (post-V1)

2. **No standalone chart-image route.** ~~Add route in `swing/web/routes/` to serve PNGs from `exports/<session>/charts/`.~~ **SHIPPED 2026-04-27** (chart-access UX dispatch, commit `772d69b`). Date-less `/charts/{ticker}.png` route; 303 redirect to existing date-prefixed StaticFiles URL or chart_scope-aware 404 with operator-facing reason.
3. **Open positions rows don't expand to chart.** ~~UX gap during trade management.~~ **SHIPPED 2026-04-27** (chart-access UX dispatch, commit `f0d13e8`). HTMX click-to-expand on dashboard open-positions rows, mirroring watchlist expand pattern. Chart inline if ticker in chart-scope; "Chart unavailable" message with chart_scope reason otherwise. **Note:** clicking dashboard's "Refresh now" button collapses any expanded rows back to compact form — expected HTMX OOB-swap behavior (the swap replaces the table HTML so transient client-side expansion state resets). Click-to-expand binding survives, but expanded VISUAL state does not. Operator confirmed this is fine.
4. **Chart-scope set misaligned with Phase 4 watchlist sort.** ~~Empirically confirmed during verification: dashboard top-5 watchlist (Phase 4 tag-aware composite sort) only overlaps chart-scope set on 1 of 5 tickers (DHC). Operator-design discussion required before implementation.~~ **SHIPPED 2026-04-28** (chart-scope policy v2 dispatch chain `c4820d0..527e334`, 15 commits). Three-tier policy `aplus > open_position > tag_aware_top_n` with N=10 watchlist top-N (default raised 5 → 10). Cross-surface drift race closed via `PipelineRunBinding` pinned at request-handler entry. Schema migration 0011 extends `pipeline_chart_targets.source` CHECK. Stop-hline omission active for None/0 stops. Wall-time monitoring active (60s WARN / 120s ERROR). Spec at `docs/superpowers/specs/2026-04-27-chart-scope-policy-v2-design.md`; plan at `docs/superpowers/plans/2026-04-27-chart-scope-policy-v2-plan.md`.

### Tier 3 — Operator-design questions

5. **Lightning icon trigger logic re-evaluation.** Current rule: `price >= 0.99 × entry_target`. Operator surfaced concern that simple "near pivot" indicator may not be the right "actionability" signal post-Phase-4 (with richer tag tier + pattern classification + hypothesis-recommendation engine). Options enumerated in verification-results doc.
6. **Multiple concurrent advisories vs single price-stop field.** Open positions can show multiple trail-stop advisories (e.g., 10MA + 20MA based) but trade row supports only one stop value. Reconciliation needed: state-machine when stop adjusted to satisfy one but not all advisories. Phase 3d follow-up. _Operator framing recorded 2026-04-27 (verification-results doc §#6): maximum-communication principle — annotate, don't suppress; trade-maturity gating concept (default 20MA early, upgrade to 10MA after ~+1.5-2R)._

### Tier 4 — Verification doc fixes — **SHIPPED 2026-04-27** (this commit)

7-14. Verification doc had SQL queries assuming `sqlite3` CLI on PATH, conflated "error" column SQL, PowerShell-incompatible Python multi-line syntax, missing "conditional on open positions" note for §1.1.a, account-card field-list overstated vs actual UI, §3 chart-image instructions assumed ticker stays in watchlist post-trade, §5.x CLI commands had wrong option names + missing required options (`--entry`/`--entry-price`, `--stop`/`--initial-stop`, missing `--entry-date` + `--shares`, `--rationale` is `click.Choice`), and chart's purple dotted "consolidation marker" lacked operator-facing legend. **All resolved in the Tier-4 doc-fix bundle commit alongside post-mathtext-fix follow-ups (below).** Full details in `docs/chart-pattern-flag-v1-manual-verification-results.md`.

### Verification deferred (re-run when conditions enable)

- §3.2 chart overlay flag-painting — needs flag classifications. Currently zero. Retest post Tier 2 #4 (chart-scope alignment) AND/OR when market produces flag patterns.
- §3.4 classifier-error chart — needs error rows. Currently zero.
- §4.3-4.5 override variants — exercise at next 2-3 trade entries via web form.
- §4.7 soft-warn × chart_pattern — needs 4+ open trades.
- §5.1 + §5.3 CLI variants — exercise at next CLI trade entry.
- §6 full cross-surface consistency — needs `pattern='flag'` ticker.

---

## 2026-04-27 chart-pattern flag-v1 mathtext fix follow-ups

Items surfaced from the Tier-1 mathtext title regression fix dispatch (commit `29c93f5`, single-task implementer dispatch with 2-round Codex review → `NO_NEW_CRITICAL_MAJOR`).

### Mathtext-hardening on the suptitle path (R1 Major; ACCEPTED out-of-scope; defer)

The Tier-1 fix dropped `$` from the chart title format string. Adversarial Codex R1 raised a defense-in-depth concern: the production path passes `title=` to `mpf.plot(...)`, which routes through `fig.suptitle` with default `parse_math=True`. If a future ticker symbol ever contains a mathtext metacharacter (`$`, `^`, `_`, unbalanced `\`), it would re-enter math mode despite the current title format being `$`-free.

Threat-model assessment: real-world US equity tickers use `[A-Z\.\-]` only; none of those characters trigger matplotlib's mathtext interpreter. Numeric formatters (`{:.2f}`) emit only digits + `.`. The current fix is sufficient for the ticker character set the framework actually consumes.

Possible future hardening if the threat model widens:

- **(a)** Switch `mpf.plot(returnfig=True)` and call `fig.suptitle(title, parse_math=False)` explicitly after — disables math-mode parsing on the suptitle entirely. Defense-in-depth at the rendering boundary.
- **(b)** `_sanitize_for_mathtext()` helper that escapes/strips `$ ^ _ \` from the ticker substring at title-construction time. Defense-in-depth at the format-string boundary.

Cheap insurance; not urgent. Pick up if the codebase ever ingests non-US tickers, derivative symbols, or any source that could put metacharacters into the ticker field.

### Mathtext metacharacter gotcha (informational; captured in CLAUDE.md gotchas)

Matplotlib mathtext fires on `$` (paired math mode), `^` (superscript), `_` (subscript), and unbalanced `\`. Future title-format additions (scientific notation, exponents, footnote markers, custom annotations) will need visual re-verification on rendered PNG, NOT just string-equality assertions. Captured in CLAUDE.md gotchas in this same housekeeping commit.

---

## 2026-04-28 chart-scope policy v2 follow-ups

Items surfaced from the chart-scope policy v2 cycle (spec `c52835f` 4-round Codex + plan `d1dc4e4` 5-round Codex + executing-plans chain `c4820d0..527e334` 2-round Codex; 15 commits total). Tier-2 #4 fully shipped; these are forward-looking deferrals or accepted-with-rationale items captured for future dispatches.

### From spec (V1-deferred items, all explicitly out-of-scope):

- **Slow-marked benchmark test for chart-step wall time.** Deterministic log-capture mechanism shipped in Task 7; real-timing benchmark deferred to `-m slow` suite or dedicated benchmark CI. Spec §A "Test instrumentation."
- **`pipeline_runs.charts_wall_time_ms` persisted column** for queryable wall-time history (currently log-only). Would require migration 0012 + write-path threading + consumer audit. Defer until operator builds external monitoring or alerting layer. Spec §A "Future V2 hardening."
- **Tier-based shedding** when wall time projected > soft budget mid-step. Skip remaining `tag_aware_top_n` tickers; add `chart_status='skipped_for_budget'` enum value. Spec §A "Future hardening." Adds complexity; only worth it if wall-time overruns become operationally common.
- **Filter-intersection alignment** between `_sort_watchlist` (web) and `_step_charts` (pipeline). Watchlist rows missing `entry_target` or `last_close` are visible on dashboard but excluded from chart-scope. Future dispatch could align filters bidirectionally. Spec §A "Residual filter-intersection limitation." Small but real coverage gap.
- **Cross-request session pinning** for inter-request races. Currently bindings pin per-request only; user clicking different rows over time may see different `data_asof_date` values across same session. Closing requires server-side cross-request session state. Spec §C "What the binding does NOT close."
- **Future surfaces composing multiple `resolve_chart_scope` calls in one handler** must add explicit shared-binding tests when they emerge. Spec §C "Technical guardrail deferral." YAGNI for V1; convert to test pin when first multi-call surface ships.

### From executing-plans dispatch (R1/R2 ACCEPTED-with-rationale):

- **Tag-aware sort `flag_tags` lookup canonicalization beyond dedup boundary** (executing-plans R1 Minor 1). `.upper()` discipline applied at dedup boundary in `_step_charts`; the flag_tags lookup keyed by raw `c.ticker` / `entry.ticker` (no `.upper()`) is acceptable in V1 because production data is consistently upper-case per spec. Defense-in-depth tightening (extend `.upper()` to all ticker references) deferred until/unless mixed-case watchlist/candidate data appears.
- **Rendered-surface (route or HTMX template) test for `out-of-scope-legacy` reason code** (executing-plans R2 Minor 2). Currently pinned only at resolver/unit-test level. Future dispatch could add a TestClient-level test asserting the rendered "Chart unavailable" surface displays the `out-of-scope-legacy` reason text. Additional test coverage; not a regression.

### Plan-implementation completed (was tracked as deferred; now resolved):

- ~~**Reviewer-checklist hardening for binding contract enforcement.**~~ INCORPORATED into plan Task 10 Step 3 (writing-plans phase R4 Minor 2 fix). Shipped as part of executing-plans Task 10 phase checkpoint.

### Future deferrals (operator-paced; explicit operator-direction required to action):

- **Chart-scope policy v3: add `hypothesis_rec` as 4th tier.** Originally deferred per hyp-recs trade-prep expansion brainstorm Q2 (2026-04-28): "Chart unavailable message for now is fine. We may eventually adjust the rules for when charts are created, that will be explicit direction from me if/when I feel the workflow needs it." **2026-04-30 reaffirm-deferral signal:** operator took CC trade (hyp-rec; Sub-A+ VCP-not-formed); chart was unavailable per design (CC not in `aplus + open_position + tag_aware_top_n`). Operator wanted to view chart for hyp-rec trade-decision; "Chart unavailable" was working as designed but cost was real. **Operator decided to keep deferring** rather than dispatch v3 now. Trigger condition was nearly hit; track future occurrences as accumulating signal. **Fix scope when picked up:** mirrors chart-scope policy v2 cycle structurally — migration 0013 extends `pipeline_chart_targets.source` CHECK to allow `'hypothesis_rec'`; resolver gains 4th tier (`aplus > open_position > tag_aware_top_n > hypothesis_rec`); pipeline `_step_charts` enumerates hyp-recs and renders charts. Cost: +5-15 chart renders per pipeline run (bounded by hyp-recs panel size). With Phase 3 OHLCV archive shipped, the yfinance cost is mostly archive cache hits. Brainstorm-skip viable when picked up — Q1-Q6-equivalent of v2 already known.

Operator surfaced the workflow gap during CC-pivot-mismatch bug triage (2026-04-28): hyp-rec rows are evaluated row-by-row against chart pattern + buy-window proximity before pulling the trigger; current dashboard surface lacks at-a-glance trade-preparation snapshot. Proposal: HTMX click-to-expand on hyp-rec rows showing the full trade-prep view, mirroring the watchlist/open-positions expand pattern but with trade-prep semantics.

Q1 disposition (2026-04-28): pure-trigger discipline conditional on price being inside the buy window — formal version of "wait for pivot, don't chase >1% above" entry-discipline (2026-04-25). The expansion makes "in-window?" check at-a-glance rather than ad-hoc.

**Brainstorm dispatch pattern:** implementer-dispatched (operator preference + brainstorm-pattern threshold met — multiple medium-complexity decisions, cross-surface scope, likely spec ≥500 lines).

### Locked decisions (operator, 2026-04-28; brainstorm uses these as framing input):

1. **Chase factor.** 1% per recorded discipline for V1, but MUST be configurable — not hard-coded. Implementation hooks into the future configuration-page work (separate todo below); for V1 the 1% lives in a config field with a sensible default. Toml-shadowing audit applies (per `aeb2084` lesson) — if a tracked toml override exists at ship time, must update in the same commit OR explicitly accept as operator opt-in.
2. **Chart in expansion when ticker is out-of-chart-scope.** "Chart unavailable" message reusing the chart-access UX pattern — same behavior as current `/charts/<TICKER>.png` handler when ticker not in chart-scope. NO chart-scope policy change for this dispatch. Operator will give explicit direction if/when chart-scope rules need adjustment.
3. **Cost-display semantics.** Show two cost numbers: risk-based (using $7,500 floor sizing) AND cash-feasible (capped at actual balance). **Cash-feasible cap uses CURRENT ACCOUNT BALANCE ONLY**, NOT total liquidity (balance + open positions). May add a risk display for both ends in V2; V1 ships shares + total cost for the two cases.
4. **Lightning icon.** Keep as-is for now. Do NOT hide or strip in this dispatch. Operator may repurpose later (Tier-3 #5 stays open as a separate conversation); the explicit reason is so the icon remains visible as a reminder for that future decision rather than evaporating.
5. **Cross-surface scope.** Hyp-recs ONLY in this dispatch. Watchlist + open-positions snapshot extensions deferred. (Watchlist's existing expand stays chart-only; open-positions' existing expand stays chart-only.)
6. **CC pivot bug bundled into this dispatch (Option C).** Watchlist `Pivot` column header currently renders `WatchlistEntry.entry_target` (frozen at add time) under a header that says "Pivot." Fix renders `candidates.pivot` (current eval-run pivot) instead — matches what hyp-recs already does. Cross-surface consistency on what "Pivot" means becomes part of this dispatch's done-criteria. Investigation already complete (survey result captured in this conversation; see CC-pivot-mismatch findings below).

### Snapshot fields to design:

The expansion content should include (V1 scope):

- **Buy stop** = `candidates.pivot` (already in hyp-rec VM)
- **Buy limit** = pivot × (1 + chase_factor); default 1%, configurable
- **Sell stop** = framework-computed initial stop (verify field — likely `stop_loss` on candidate row OR computed via existing sizing pipeline)
- **# shares (risk-based)** = risk-based position size from `compute_shares` (uses max($7,500 floor, balance) per project memory)
- **# shares (cash-feasible)** = same calc capped at floor(account_balance / pivot) — based on CURRENT BALANCE ONLY, not balance + open positions
- **Total cost (risk-based)** = risk-based-shares × pivot
- **Total cost (cash-feasible)** = cash-feasible-shares × pivot
- **Chart** = inline if ticker in chart-scope; "Chart unavailable" with reason if not (current chart-access UX behavior, no policy change)

### CC pivot mismatch bug (bundled — investigation already complete):

- **Symptom:** Watchlist row for ticker CC shows "$24.13" under "Pivot" column header; hyp-recs table shows "$26.98" for same ticker. Same price ($25.70 stale in both), divergent pivot.
- **Root cause:** Watchlist row partial at `swing/web/templates/partials/watchlist_row.html.j2:16` renders `w.entry_target` (frozen at add time, immutable) under a column header at `swing/web/templates/partials/watchlist_top5_section.html.j2:4` that says "Pivot." `WatchlistEntry.last_pivot` field exists in the model but is never rendered. Hyp-recs correctly renders `candidates.pivot` from the latest eval run.
- **NOT mixed-anchor:** Both surfaces bind to the same evaluation_run via `latest_evaluation_run_id`. The 2026-04-25 mixed-anchor closure was anchor-focused and missed cross-surface field-rendering audit.
- **Fix as part of this dispatch (Option C):** watchlist row partial renders current pivot from candidates dict (joined by ticker, same as hyp-recs does) under "Pivot" header. Header label stays "Pivot," semantics align across both surfaces.
- **Lightning icon (per Q4):** trigger logic stays bound to `entry_target` unchanged. Fix scope is column-display only (`watchlist_row.html.j2:16`); lightning trigger at `watchlist_row.html.j2:7` is NOT touched. Behavioral consequence: CC's lightning continues firing post-fix (price $25.70 ≥ 0.99 × $24.13 entry_target). **Semantic side-effect operator should be aware of:** column header "Pivot" will render `candidates.pivot` ($26.98) while lightning math uses the unshown `entry_target` ($24.13), so a row may show "lightning fires" without the displayed pivot supporting the math. This is the deliberate cost of preserving lightning behavior (Q4) independently of column-display semantics (Q6). Tier-3 #5 (lightning re-evaluation) remains the venue for revisiting trigger field; this dispatch does NOT touch it.

### New lesson (capture in housekeeping when this dispatch ships):

**Anchor closure surveys must also audit template field rendering, not just query anchors.** The 2026-04-25 mixed-anchor closure verified `MAX(run_ts) FROM evaluation_runs` was gone from the web layer, but did not audit which fields were rendered in templates under shared column names. Same anchor with different rendered fields still produces operator-visible cross-surface divergence (CC pivot mismatch is the canonical example). For future cross-surface consistency reviews: anchor parity AND field-rendering parity are independent audit dimensions.

### Cross-references:

- Tier-3 #5 lightning re-evaluation (`docs/phase3e-todo.md` 2026-04-27 manual-verification findings) — stays separate per operator; expansion redesign supersedes some of its scope but operator wants the lightning visible for now.
- Configuration-page future feature (separate todo below).
- Sub-A+ VCP-not-formed hypothesis trade discipline (orchestrator-context 2026-04-25 "Entry discipline for hypothesis trades: wait for pivot").
- Capital-risk-floor convention (project memory `project_capital_risk_floor.md`) — sizing uses max($7,500, balance); cash-feasibility uses balance only.

---

## 2026-04-28 configuration page for operator-tunable settings — **SHIPPED 2026-05-02 at `3a4195c`**

Operator surfaced 2026-04-28: as small operator-tunable settings accumulate (chase_factor, chart_top_n_watch, risk_pct floor, account balance cap rules, etc.), each currently lives as a Python default + tracked toml override in `swing.config.toml`. Future feature: dashboard configuration page where operator can view + edit these values without manual toml-editing.

**Locked decisions** (operator + orchestrator 2026-05-01): see `docs/phase5-configuration-page-writing-plans-brief.md` §2 — separate user-config file at `%USERPROFILE%/swing-data/user-config.toml`; precedence default → tracked toml → user-config → page-write; per-request read; dedicated `/config` page; CLI parity (`swing config show|set|reset`); 3 V1 fields.

**V1 field set (3 fields; canonical paths from plan §A consumer audit, NOT the speculative paths in the brief):**

- `cfg.web.chase_factor` (default `0.01`; consumed at 2 sites — hyp-recs trade-prep expansion view-model). NOT top-level as the brief originally speculated.
- `cfg.pipeline.chart_top_n_watch` (default `10`; consumed at 7 sites). NOT under `web.` as the brief originally speculated.
- `cfg.account.risk_equity_floor` (default `7500.0`; **already** present in tracked `swing.config.toml:22`; consumed at 3 production sites — `swing/pipeline/runner.py:424`, `:558`, `swing/web/view_models/dashboard.py:496`). Brief's "currently a code constant" assertion was WRONG; Task 0a became a no-op.

**Toml-shadowing audit (binding):** any field surfaced via the config page MUST honor the toml-shadowing lesson (`aeb2084`, 2026-04-28). Read order resolved 2026-05-01: Python default → tracked `swing.config.toml` → user-config.toml → page-write (which writes user-config.toml). User-config strictly overrides tracked-toml per-field. Pre-flight `grep -rn "<field_name>" .` audit on every field surfaced (canonicalized into plan §C).

**Future field additions:** small per-field follow-ups — V1 infrastructure ships ready for them. Candidates surveyed but explicitly NOT V1: `risk_pct`, `pipeline_lease_wait_seconds`, `current_balance`, advisory thresholds (10MA / 20MA / etc.), other `cfg.web.*` settings.

**Executing-plans first attempt** (commit chain `dff70ca..2278e97`, 2026-05-01): landed Tasks 1.0/1.1/1.2/2.0 plan-aligned (`dff70ca`, `db1bf0f`, `0b85046`, `e42f5be`); fifth commit `2278e97` was a rogue Task 1.2 rewrite (overwrote landed plan-aligned `swing/config_overrides.py` with a non-plan API; absorbed Task 2.1 wiring under wrong subject; created non-plan test file with `Path.cwd()` mkdtemp pattern yielding 66 ACL-locked `.config-overrides-*` dirs at repo root). Diagnosed as extended-time-window subagent self-collision within `subagent-driven-development` (NOT external interference; 9:47 min between duplicate Task 1.2 commits with intervening Task 2.0 commit). Reverted via `git reset --hard e42f5be` + `git push --force-with-lease origin main`.

**Executing-plans re-dispatch (2026-05-02):** worktree-isolated on `phase5-config-page-redispatch` branch with global PreToolUse Codex-blocking hook + marker-file workflow. 7 commits onto branch (`f86eafd..4d3174d`); 2 Codex rounds → NO_NEW_CRITICAL_MAJOR; operator-witnessed 6-step browser gate PASS. Merged via `git merge --no-ff` at `3a4195c` (4 docs commits ahead of base prevented fast-forward). 1381 → 1472 fast tests (+91, exceeds the +75 plan estimate). Browser-gate workaround: PowerShell prefix `$env:PYTHONPATH = "."; python -m swing.cli web` to overcome editable-install-vs-worktree path mismatch.

**V1 follow-ups (out-of-scope discoveries from re-dispatch return report; OPEN):**

- **CSS gap on new config-page surfaces.** `.banner.warn`, `.banner.error`, `.btn`, `.btn-secondary` classes referenced in `swing/web/templates/config.html.j2` + `partials/config_hard_refuse.html.j2` + `partials/config_soft_warn_confirm.html.j2` may not be defined in `swing/web/static/app.css`. Page is functional; banners may render as plain text instead of styled. Cosmetic polish ticket.
- **`ConfigPageVM.session_date` inconsistency.** Uses `date.today().isoformat()` instead of `action_session_for_run(datetime.now())` like other base-layout VMs. Cosmetic — affects topbar date display only on weekends/holidays/HST. Fix would touch landed Task 4.0 file (Watch item #12 prohibited within-dispatch); now post-merge it's safe to fix.
- **Route-layer integration smoke gap.** Task 2.1 override-applied test exercises the VM helper directly (not via TestClient round-trip). The 26 route-wiring sites are grep-verifiable; future task could add a TestClient-based smoke that POSTs/GETs one of the patched routes after writing user-config to assert the rendered response reflects the override. Not blocking V1 ship.
- **Schema-valid wrong-type user-config crashes `_get`.** R1 Minor 1 advisory. V2 hardening: add `isinstance(section_obj, dict)` guard. Surfaces as visible 500 (not silent corruption); operator hand-edit error scope only.
- **Lost-update race across two browser tabs** (R1 Major 3 ACCEPTED). Single-operator scope per CLAUDE.md + brief §3.2; two-tab race operationally implausible. V2 may add file locking if multi-user surface ever emerges.

**Cleanup deferred (operational housekeeping; bundled):** 66 ACL-locked `.config-overrides-*` dirs + `.codex-pytest-6681924b-*` dir + `.tmp` + `.tmp_pytest` + `pytest-run-*` dir + `.worktrees/phase5-config-page-redispatch/` (worktree branch + git registration removed; directory removal blocked by file handles when tested 2026-05-02). All owned by `AughtSevernIII\CodexSandboxOffline` per the dry-run output. `cleanup-locked-scratch-dirs.ps1` allowlist extended 2026-05-02 to recognize the new patterns; needs operator-elevated PowerShell to execute.

**Cross-references:**
- Brief (writing-plans): `docs/phase5-configuration-page-writing-plans-brief.md` (commit `3fde496`).
- Plan: `docs/superpowers/plans/2026-05-01-configuration-page-plan.md` (HEAD `e8c6396`; ~75 new tests planned; 5 Codex rounds → NO_NEW_CRITICAL_MAJOR).
- Brief (executing-plans, REVISED): `docs/phase5-configuration-page-executing-plans-brief.md` (`671451f`; worktree isolation + Task 2.1+ starting point).
- toml-shadowing lesson in `docs/orchestrator-context.md` Lessons captured (post-`aeb2084`).
- Subagent self-collision lessons in `docs/orchestrator-context.md` Lessons captured (chart-pattern Phase 2 tight-window 2026-04-26; Phase 5 extended-window 2026-05-01).
- `project_capital_risk_floor.md` memory.

---

## 2026-04-28 OHLCV archive consolidation (QUEUED; Medium effort)

Operator surfaced 2026-04-28 during research-resource discussion: "are we archiving any of the yfinance data we are pulling down? One way to improve throughput would be to start creating a local history which could be queried for all historical data, only using yfinance to pull down the most recent OHLCV numbers." Survey of current code found three caching paths with inconsistent semantics:

### Current state (orchestrator survey 2026-04-28):

1. **`swing/prices.py PriceFetcher` → `~/swing-data/prices-cache/`.** On-disk parquet cache. Used by pipeline runner, CLI commands, weather runner. **53 MB, 5,521 files.** Keying is wasteful: `{ticker}_{lookback_days}d_asof-{YYYY-MM-DD}.parquet` produces a new file per as_of_date even when 99% of the data overlaps. AAPL alone has separate parquets for 8+ as-of-dates over 2 weeks; same 120-day window re-stored each session. ~200-300 unique tickers represented across 5,521 redundant snapshots.
2. **`swing/pipeline/ohlcv.py` (chart-step OHLCV).** Used by `_step_charts` to feed chart rendering AND chart-pattern flag-v1 classifier. **No disk cache.** Fresh `yf.Ticker.history(...)` pull every pipeline run for chart-scope tickers (open positions + tag-aware top-N + A+ ≈ 5-15 tickers/run, all re-pulled).
3. **`swing/web/ohlcv_cache.py OhlcvCache`.** TTL-cached in-memory (3600s default), sliding-window circuit breaker. Used for dashboard SMA advisories on open positions. **Restart-flushed.** Not persisted.
4. **`~/swing-data/research-cache/ohlcv/`** (research branch). **92 MB across 2,603 ticker files.** One file per ticker (NOT per as_of_date) — the proper incremental-archive pattern. Used by research-branch harness; production paths don't consume it.

### The architectural gap:

Production paths (#1 + #2) re-fetch from yfinance every run for data that's already on disk in the research cache (#4). The proper incremental-archive pattern exists in the codebase — just not used by production. Migration to per-ticker incremental cache cuts per-run yfinance call volume by ~99% for established tickers.

### V1 scope (this dispatch):

1. **Consolidate `prices-cache/` keying.** Switch `PriceFetcher` from per-as-of-date parquet files to per-ticker parquets with date-range tracking. New file format: `{TICKER}.parquet` with `as_of_max` metadata or column. One-time migration script consolidates the 5,521 redundant files into ~200-300 per-ticker files.
2. **Add disk archive to `_step_charts` chart-fetch path.** Wrap `swing/pipeline/ohlcv.py`'s `yf.Ticker(t).history(...)` in a per-ticker incremental-fetch helper. On each call: read latest stored bar for ticker; pull yfinance for `latest+1` → today; append. New tickers get full history pull.
3. **(Optional V1) Back `OhlcvCache` with the disk archive for warm-restart.** Currently the in-memory TTL flushes on every web restart. Backing it with the same disk archive eliminates the cold-start fetch storm after restart.

### Open design questions for brainstorm/spec:

- **Corporate-action retroactive adjustment policy.** yfinance retroactively adjusts splits/dividends. A "permanent archive" with stale adjustments diverges from current yfinance over time. Mitigation options:
  - (a) **Periodic full-refresh on active tickers** (e.g., weekly cron OR on first-pull-of-session detection). Simple; small wasted bandwidth.
  - (b) **Store both raw + adjustment-factor columns separately**; recompute adjustments on access from the latest known split/dividend ratios. More complex; closer to a real time-series database.
  - (c) **Accept staleness on tickers without recent corporate actions; explicit refresh on operator-flagged tickers.** Pragmatic; requires corporate-action detection or operator-driven invalidation.
  - Default-recommendation for V1: (a) — simplest, wastes ~10-20% bandwidth on weekly full-refresh of active tickers, but tolerates the asymmetry.
- **Cache-coherence policy.** Need explicit rule for "trust archive" vs "re-fetch fresh." Probably keyed on (ticker, last_corporate_action_check_date) with explicit TTL on the corporate-action check.
- **Migration strategy for 5,521 redundant files.** One-time consolidation script; runs once, then archived/deleted. Preserve any uniquely-historic data (oldest as_of_date per ticker) before consolidation.
- **Schema location.** Is the archive a per-ticker parquet (current research-cache pattern), or a single SQLite table with composite key (ticker, date)? Parquet is faster for long history scans; SQLite integrates with existing infrastructure. Both fit; design choice.

### V1-deferred / V2:

- 1-min intraday bars (would multiply storage by ~390× — ~37 GB for full universe; out of V1 scope; framework is daily-cycle).
- Cross-platform sync (Drive-synced archive would require careful WAL-mode handling per the SQLite-DB-location invariant). Out of V1 scope.
- Automatic universe expansion (auto-archiving tickers operator hasn't asked about). V1 archives only what production paths request; demand-driven not pre-emptive.

### Storage budget (concrete):

| Universe | Tickers | 5-year history | Notes |
|---|---|---|---|
| Operator's Finviz pool only | ~500 | ~18 MB | Demand-driven minimum |
| SPX + NDX + S&P 1500 | ~1,500-2,000 | ~70-100 MB | Reasonable target |
| Full Russell 3000 | ~3,000 | ~110 MB | Comprehensive |
| 10-year Russell 3000 | ~3,000 | ~220 MB | Decadal coverage |

Storage is essentially free at all scales relevant to this project. Real value is yfinance rate-limit relief + pipeline speed + research-branch parity + diagnostic capability for any-time-window analysis.

### Cross-references:
- yfinance rate-limit + threading gotcha in CLAUDE.md gotchas.
- `swing/prices.py:24` `PriceFetcher` (Phase 2 carve-out territory).
- `swing/pipeline/ohlcv.py` (no current cache).
- `swing/web/ohlcv_cache.py` (in-memory TTL).
- `~/swing-data/research-cache/ohlcv/` existing pattern (use as architectural reference).

---

## 2026-04-28 sector/industry capture + display (QUEUED; Medium effort)

Operator-recall surfaced 2026-04-28: "At some point several days ago there was a discussion about capturing which industry the tickers fall under and displaying/capturing that as a data point which might be useful for making a trade determination." Orchestrator survey confirmed: data is INGESTED but DROPPED on the production path. Never persisted, displayed, or used in decision logic.

### Current state (orchestrator survey 2026-04-28):

- **Ingested.** Finviz CSV schema validator at `swing/pipeline/finviz_schema.py:12` requires both `Sector` and `Industry` columns. CSV is rejected to `data/finviz-inbox/rejected/` if either column is missing.
- **Not persisted.** Zero hits for `sector`/`industry` columns anywhere in `swing/data/` (11 migrations + repo files + dataclass models surveyed). The fields are read from the CSV and discarded.
- **Not displayed.** No template, VM, or route consumes sector/industry data.
- **Not used in decision logic.** Only mention in production code outside the Finviz schema is a comment in `swing/trades/stop_adjust.py:31` about the "news" rationale enum value.
- **But the framework PRESUMES sector analysis happens.** orchestrator-context.md lines 156–157 explicitly include sector in operator's manual decision process: "Operator validates the recommendation (chart pattern, risk, **sector preference**)..." — operator currently has to look up sector externally per ticker because the framework drops the data.

### V1 scope (this dispatch):

Mirrors the `hypothesis_label` and `chart_pattern_*` patterns already shipped (snapshot-at-entry-surface frozen-at-entry):

1. **Schema migration 0012** — add `sector TEXT NOT NULL DEFAULT ''` and `industry TEXT NOT NULL DEFAULT ''` columns to `candidates` table (refreshed each pipeline run from Finviz CSV). Add same columns to `trades` table (frozen at entry, mirrors `hypothesis_label`).
2. **Pipeline ingestion** — `_step_evaluate` writes Sector/Industry from each Finviz CSV row into the candidate row. Already-validated by schema; just needs to flow to persistence.
3. **VM + template surface** — display sector/industry on the surfaces where operator decision happens:
   - Hyp-recs row expansion (NEW; coordinates with hyp-recs trade-prep expansion dispatch — see "Sequencing question" below).
   - Watchlist row expansion.
   - Trade entry form (read-only field showing the snapshot value to be persisted).
   - Open positions row (informational; operator can confirm what they bought).
4. **Trade entry capture** — frozen-at-entry like `hypothesis_label`. Captured via the snapshot-at-entry-surface ToCToU pattern (spec §3.6 / Phase 5). `EntryRequest` carries `sector` + `industry`; `record_entry` persists what's passed AS-IS.

### Open design questions for brainstorm/spec:

1. **Granularity.** Finviz provides Sector (~11 broad: Technology, Healthcare, Financial Services, Energy, etc.) AND Industry (~150 narrow: Software-Infrastructure, Biotechnology, Banks-Regional, Oil-Gas-E&P, etc.). Show both? Show only sector? Show industry but group by sector? Recommendation: persist both, display both — sector for grouping/concentration, industry for context. Cheap to defer the granularity decision to display-time.
2. **Display surfaces.** Hyp-recs row expansion is obvious. Watchlist row expansion likewise. Trade entry form likely. Open positions row? Journal review? Each surface is a small-incremental cost. Suggested V1 scope: 4 surfaces (hyp-recs expansion, watchlist expansion, trade entry, open positions). Defer journal review aggregation to V2.
3. **Snapshot vs always-current.** Sector/industry are very stable for a ticker (rarely change — corporate restructuring is the main driver). Both approaches work:
   - **Frozen-at-entry** (matches `hypothesis_label` / `chart_pattern_*` patterns; consistent with framework's pre-registration discipline).
   - **Always-current** (read from latest candidate row at display time; no persistence on `trades`).
   - Recommendation: frozen-at-entry per the existing pattern. If sector data drifts post-entry due to ticker reclassification, that's information worth preserving (the operator entered when this ticker was Tech; it's now Industrials — the analysis should know that).
4. **Sector source-of-truth.** Finviz only. yfinance has its own sector taxonomy that differs from Finviz. Don't reconcile across sources in V1 — Finviz is the single authoritative source for the framework's sector view.

### V2 follow-up (gated on V1 shipping):

- **Sector concentration warning surface.** Once sector is captured on `trades`, dashboard could surface "you have 3 open positions in Technology, max-sector-concentration N% of risk" warnings. Prevents over-concentration in a single sector. Configurable cap (e.g., max 50% of total open risk in a single sector). Separate dispatch; ungated on V1 shipping.
- **Industry-level concentration** (probably NOT useful for a $7,500 account at 5 concurrent positions; sector-level is the right granularity at this scale).
- **Sector-level analytics on `swing trade analyze`.** Group historical trades by sector; per-sector expectancy, win rate, R-multiple. Useful for identifying operator's per-sector edge (or anti-edge). Separate dispatch.

### Sequencing question:

Sector/industry display surfaces include **hyp-recs row expansion** — which is the central artifact of the just-queued hyp-recs trade-prep expansion brainstorm (`docs/phase3e-todo.md` 2026-04-28 hyp-recs trade-prep expansion section). Two ways to sequence:

- **(A) Fold sector/industry into the hyp-recs expansion brainstorm** — the snapshot expansion already designs a multi-line context display for hyp-rec rows; sector/industry fits naturally as additional context fields. Avoids a second dispatch on overlapping surface. Sector-capture migration becomes a prerequisite (Task 0a) of the hyp-recs expansion plan.
- **(B) Ship sector/industry capture FIRST as a small standalone migration** — schema 0012 + pipeline ingestion + minimal display (4 surfaces, all read-only). Then hyp-recs expansion brainstorm starts with sector data already captured and queryable.

Recommendation: **(B)**. Sector capture is a tighter, more bounded scope (just data flow + display); hyp-recs expansion can consume the captured field without scope creep on its brainstorm. Keeps the brainstorm focused on its own design questions (chase factor, cost-display semantics, etc.) without adding sector-granularity questions.

### Cross-references:
- `swing/pipeline/finviz_schema.py:12` (validator requires both columns; data flows in this far and stops).
- orchestrator-context.md lines 156-157 (framework-presumes-sector-analysis already in decision-making).
- `hypothesis_label` and `chart_pattern_*` patterns (snapshot-at-entry-surface frozen-at-entry; existing repo precedent).
- 2026-04-28 hyp-recs trade-prep expansion section above (sequencing-question dependency).

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

## 2026-05-01 Journal v1.2 incorporation (Phases 6-9)

Sourced from operator-commissioned research at `future/swing_trading_journal_ai_ingestion_v1.2.md` (and the v1.0 → v1.1 → v1.2 evolution chain at `future/swing_trading_journal_*.md`). v1.2 is a discretionary-trader's journal spec; OUR platform is a framework-research-loop. The phases below adopt v1.2's discipline scaffold WHERE it adds value over our existing infrastructure, modify it WHERE its assumptions conflict with our framework-driven flow, and DROP elements we don't need (pyramiding, Setup_Playbook as DB rows, Screen_Definitions versioning).

**Umbrella sequencing decision (operator 2026-05-01):** Decompose into four phases by value × independence; ship Phase 6 first as the cheapest highest-value piece, re-evaluate before committing to Phase 7's larger schema disruption.

### Cross-cutting framing (applies to all four phases):

- **v1.2 assumes self-rated quality scoring.** Drop self-rated components that the pipeline asserts (valid setup, regime supportive, sector supportive). Keep operator-only fields (emotional_state, confidence_score, manual override-of-doctrine).
- **v1.2 assumes operator-composed thesis.** Adapt to "thesis = pipeline bucket + criteria tags + hypothesis_label" + operator-added context (why_now, invalidation_condition).
- **v1.2's `trade_origin` enum** maps onto our actual ingestion paths: `pipeline_aplus`, `pipeline_watch_hyp_recs`, `pipeline_watch_manual`, `manual_off_pipeline` (4-value, NOT v1.2's 7-value discretionary enum).
- **Setup_Playbook as DB entity:** DROP. Our setups are encoded in `swing/evaluation/scoring.py` + `criteria.py`; v1.2's setup_id maps to our `hypothesis_id` + doctrine layer.
- **Screen_Definitions versioning:** DROP. `finviz_schema.py` is git-versioned; explicit screen-version entity adds friction without value.
- **Pyramiding R-views (R_initial / R_effective / R_campaign):** DROP. Operator at $7,500 capital, 5 concurrent, no pyramiding plan.
- **Drawdown circuit breaker:** v1.2 defaults this opt-in disabled; align (do not enable by default).

### Phase 6 — Post-trade review surface — **SHIPPED 2026-05-04 at `51c79ed`**

**Bundle:** Mistake_Tags + Process Grade A-F + `mistake_cost_R` / `lucky_violation_R` + `lesson_learned` + Review_Log cadence skeleton.

**Why first:** Highest-value piece; ships independently of state-machine work; closes a real gap (operator memory + ad-hoc review today is the only behavioral discipline measurement). Cheap and additive — touches the post-close path only, no schema disruption to open-trade flow.

**Scope:**
- New schema migration: `mistake_tags TEXT` (JSON-list) + `process_grade TEXT (A/B/C/D/F)` + `entry_grade` + `management_grade` + `exit_grade` + `disqualifying_process_violation BOOLEAN` + `mistake_cost_R REAL` + `lucky_violation_R REAL` + `mistake_cost_confidence TEXT (high/medium/low)` + `lesson_learned TEXT` + `reviewed_at DATETIME` on `trades`. All nullable until reviewed.
- New `Review_Log` entity: `review_id, review_type (daily/weekly/monthly/quarterly), period_start, period_end, scheduled_date, completed_date, skipped, duration_minutes, n_trades_reviewed, total_mistake_cost_R, total_lucky_violation_R, primary_lesson, next_period_focus`. Cadence compliance dashboard surface.
- Mistake_Tags taxonomy from v1.2 §7.10: 5 categories (entry / risk / management / psychology / reconciliation) + `none_observed`. Adopted nearly as-is; this is sound classification work the operator shouldn't re-derive.
- Process Grade computation per v1.2 §9.2: weighted (entry 0.40 / management 0.35 / exit 0.25) with disqualifying floor (any-stage-F → F; disqualifying_process_violation → max D).
- `swing trade review <trade_id>` CLI command + web `/trades/<id>/review` form. Required at close + within 7 days (configurable).

**Estimated dispatches:** 2 (one for the schema + repo + CLI; one for the web form + dashboard surface). Brainstorm-skip viable; copowers:writing-plans direct.

**Actually shipped as:** single executing-plans dispatch on worktree branch `phase6-post-trade-review` (not split). 24 commits (16 task-impl + 1 code-review I2 + 4 R1 Codex fixes + 1 R2 Codex minor + 1 mid-verification I3 fix). 2 Codex rounds → NO_NEW_CRITICAL_MAJOR. Operator-witnessed 6-surface browser gate PASS. Test count 1472 → 1587 (+115 vs plan's +30-45 estimate; ~3x due to Codex compound-ROI on discriminating-test-discipline). Ruff 98 → 80 (incidental cleanup). 0 rogue commits — first all-clean executing-plans dispatch since Phase 4.

**V1 follow-ups (out-of-scope discoveries from executing-plans return + operator-witnessed verification gate; OPEN):**

- **Cadence card lacks clickable "Complete review" link.** Operator-witnessed gate finding 2026-05-04. Cadence cards at `swing/web/templates/partials/cadence_cards.html.j2` render period + scheduled/completed status but have NO link to the completion form. Operator navigated via direct URL (`/reviews/{review_id}/complete`) for verification. Cosmetic UX gap; non-blocking. Fix: add `<a href="/reviews/{{ card.review_id }}/complete">Complete review</a>` when `card.is_pending`.
- **Completion route 404s for already-completed Review_Logs (no read-only view).** Operator-witnessed gate finding 2026-05-04. `GET /reviews/{id}/complete` at `swing/web/routes/trades.py:1126` explicitly checks completion state and returns 404 with `"Review #N not found or already completed"`. Operator could not revisit completed Review_Log via UI to verify frozen aggregates (verification done via direct DB query instead). Fix options: (a) modify the existing GET handler to render read-only view for completed rows, OR (b) add new `GET /reviews/{id}` route for read-only display.
- **`ReviewsPendingVM.window_days` field stale after Codex R1 Major 1 fix.** Codex R2 Minor 3 ACCEPTED-with-rationale 2026-05-04. R1 Major 1 fix changed `/reviews/pending` list view from "overdue only" to "ALL closed unreviewed" semantic; the `window_days` field is no longer rendered on the page but still carried on the VM. Future cleanup: drop the field OR re-purpose for "highlight trades older than the badge threshold" UI surface.
- **Migration head-version test consolidation needed.** Phase 6 Task 1 code-review finding 2026-05-04 (pre-existing structural debt amplified by every schema bump). `tests/data/test_migration_0010_trade_chart_pattern.py` has hard-coded `assert version == 13` inside a migration-0010-specific test; same inline assertion exists in other migration-specific tests. Each schema bump requires retroactive updates across multiple test files (Phase 6 had to update 3). Fix: extract head-version assertions into a single `tests/data/test_expected_schema_version_is_current` test and drop the in-line versions from migration-specific tests.
- **Soft-warn dismiss-link uses raw onclick.** Phase 6 review_soft_warn_close partial uses `onclick="..."` for the dismiss action (existing project pattern; not Phase 6's introduction). Flag for future HTMX-everywhere migration when the project's JS posture solidifies.
- **HX-Redirect target route must be verified to exist (test pattern strengthening).** Operator-witnessed gate found Phase 6 review POST emitted `HX-Redirect: /trades` but no `GET /trades` route was registered (fixed inline as code-review I3 to `/reviews/pending`). Future tests for HX-Redirect-emitting handlers should either (a) assert target route is registered in app's route table (e.g., `assert any(r.path == target for r in app.routes)`), OR (b) follow the redirect with a second TestClient call and assert 200. Add to writing-plans phase as checklist item for any HX-Redirect-emitting handler.

**Process-meta items captured (out-of-scope for Phase 6 V1 follow-up; informational):**

- **Copowers session state file convention doesn't share across worktrees of the same repo.** Implementer return-report observation 2026-05-04. Convention uses `sha256(repo_root_path)[:12]` for the session-state filename at `/tmp/.copowers-session-<hash>.json`; worktree paths produce different hashes than main paths, so each worktree gets its own session state file. Could be improved with `git rev-parse --git-common-dir` for shared state across worktrees of the same repo. Upstream improvement note for the copowers plugin; not Phase 6 work.
- **Subagent monthly usage limits forced 2 completions to orchestrator-session fallback.** Implementer return-report observation 2026-05-04. Two subagent dispatches hit "monthly usage limit" mid-task (one during ruff cleanup, one during Codex R1 fixes); implementer completed those workflows directly from the orchestrator session with the same end-state. Resource-awareness flag for org-budget if dispatching again soon.

**Cross-references:**
- `future/swing_trading_journal_ai_ingestion_v1.2.md` §7.10 (Mistake_Tags), §7.11 (Review_Log), §9.2 (Process Grade), §8.8 (Mistake Cost / Lucky Violation), §10.4 (Post-Trade Review workflow).
- Existing primitive precursor: `swing trade analyze <trade_id>` (Phase 3e 2026-04-25) — manual case-study output. Phase 6 upgrades this to structured + persisted.
- Existing audit-log: `trade_events` — keep distinct from Review_Log (events are state changes; reviews are aggregations).
- Writing-plans brief: `docs/phase6-post-trade-review-writing-plans-brief.md` (`441e22a`).
- Plan: `docs/superpowers/plans/2026-05-02-phase6-post-trade-review-plan.md` (commit chain `1be4622..e976d64`; 5 Codex rounds → NO_NEW_CRITICAL_MAJOR).
- Executing-plans brief: `docs/phase6-post-trade-review-executing-plans-brief.md` (`a7c4bda`).
- Ad-hoc DB cleanups: 2026-05-04 SPY test entries removed (`swing-pre-spy-cleanup-20260504T022932.db`); see orchestrator-context.md.

### Phase 7 — Trade lifecycle state machine + Fills first-class (Sub-A SHIPPED on worktree 2026-05-04; Sub-B + Sub-C chained from Sub-A)

**Sub-A SHIPPED** 2026-05-04 on worktree branch `phase7-sub-a-schema` (HEAD `78c7005`; baseline `eba1625`; 14 commits = 11 task + 2 code-review fix + 1 Codex fix; 2 Codex rounds → NO_NEW_CRITICAL_MAJOR). Migration 0014 verified working on production-shape fixture (VIR/DHC/CC/YOU FIRM values reproduced exactly); 4 preservation invariant fixtures green; backup-runner discipline operationalized with 4 integrity checks + rollback-on-partial-failure. Test delta: +102 new tests (vs ~+87 plan estimate) but 217 failed + 20 errors remain across Sub-B/Sub-C territory (web view models, journal predicate rewrites, exit/stop_adjust/review services, CLI predicate rewrites — see binding-green-gate-vs-carve-out conflict below). Ruff baseline preserved at 80.

**Chained-branch posture decision** (operator 2026-05-04): Sub-A's binding green gate at T6 was structurally impossible given plan §3 carve-out assigning predicate rewrites to Sub-B/Sub-C. Implementer surfaced the conflict; operator chose option (a) — Sub-A NOT merged to main; Sub-B + Sub-C dispatch from chained worktree branches based on Sub-A; integration `git merge --no-ff phase7-sub-c-web` to main only after Sub-C ships full suite green. **Production DB stays at v13 throughout** (no migration triggered until merge); operator's trade workflows (DHC/CC/YOU stop-adjusts, exits, reviews) continue working unaffected. Lesson captured in orchestrator-context lessons-captured 2026-05-04.

**Sub-B SHIPPED** 2026-05-04 on chained worktree branch `phase7-sub-b-services` (HEAD `71ddb95`; baseline `78c7005`; 15 commits = 9 task + 6 Codex fix; 6 Codex rounds → NO_NEW_CRITICAL_MAJOR; suite 1450→1605 passed [+155]; 217→130 failed [Sub-B territory closed]; 20→6 errors; ruff baseline 79 [-1 from 80]; zero web modifications; one authorized Sub-A territory exception — 8-line docstring at `swing/data/repos/trades.py:insert_trade_with_event` per R2 Minor 1 deferral). 6-round Codex chain was convergence (datetime canonicalization touched 5 service entry points), NOT thrash — lesson captured.

**Shim removal status (Sub-B partial; full deletion deferred to Sub-C scope decision):**
- Exit service consumption: DELETED in B.4 (`swing/trades/exit.py` no longer imports Exit/insert_exit_with_event/list_exits_for_trade).
- `tos_import.py` exits-table reads: MIGRATED to fills repo in B.9.
- Other shim consumers: ~18 files PRESERVED (web extended + review_log + pipeline + recommendations/hypothesis + journal aggregation + cli list + trades/equity + 3 test fixtures). Full shim deletion blocked on these consumer migrations — see Sub-C scope decision below.

**Sub-C scope decision (operator-paced)** — implementer's open question 2026-05-04: shim full-deletion requires migrating ~18 out-of-original-Sub-C-scope consumer files. Options:
- (A) Sub-C nominal scope (web only per plan §3); shims remain alive permanently or via future cleanup dispatch.
- (B) Sub-C extended scope: web migration + shim cleanup sweep + shim deletion in single dispatch (~12-14 tasks; ~4-7 Codex rounds; clean Phase 7 endgame).
- (C) Sub-C nominal scope ships first; separate Sub-D dispatch handles shim cleanup sweep + deletion.
Operator decision required before drafting Sub-C brief.

**Sub-C pre-conditions (binding for future dispatch after scope decision):**
1. **BASELINE_SHA = `71ddb95`** (Sub-B worktree HEAD).
2. **Worktree branch `phase7-sub-c-web`** based on `phase7-sub-b-services` (chained from Sub-B).
3. **Sub-C's done criteria gate is FULL-SUITE-GREEN** (this is the integration gate; restoring main to green via the final merge).
4. **Operator-witnessed browser verification gate is BINDING for Sub-C end** (per Phase 7 binding convention; HTMX-driven UX cannot be verified by TestClient alone).
5. **Final integration merge after Sub-C ships green**: `git checkout main && git merge --no-ff phase7-sub-c-web -m "Merge phase7-sub-c-web into main: Phase 7 (Sub-A + Sub-B + Sub-C integrated)"`. Brings all 3 sub-dispatches' work in single merge commit. Production DB triggers 0014 migration on first `swing` invocation post-merge (backup-runner discipline applies).

**Sub-B pre-conditions** (historical; SATISFIED at dispatch time):
1. ✅ BASELINE_SHA = `78c7005` (Sub-A worktree HEAD).
2. ✅ Worktree branch `phase7-sub-b-services` chained from `phase7-sub-a-schema`.
3. ✅ Done criteria gate: partial-suite-green met (Sub-A + Sub-B tests GREEN; Sub-C tests stay RED until Sub-C).
4. ✅ Shim removal partial per implementer constraint (B.4 exit service migrated; full deletion deferred per scope of remaining consumers).
5. ✅ R2 Minor 1 deferral handled at B.1 (defensive docstring) + B.3 (atomic record_entry flow).
6. ✅ Vocabulary already locked.
7. ✅ Main during Sub-B window: only docs-only commits per discipline (operator-aware Sub-B-pre-empt YOU-trade migration `eba1625` was pre-dispatch; no in-flight commits).

**Sub-C pre-conditions (binding for future dispatch after Sub-B):**
1. **BASELINE_SHA = Sub-B worktree HEAD** (chained from `phase7-sub-b-services`).
2. **Worktree branch `phase7-sub-c-web`** based on `phase7-sub-b-services`.
3. **Sub-C's done criteria gate is FULL-SUITE-GREEN** (this is the integration gate; restoring main to green via the final merge).
4. **Shim deletion completes at Sub-C T1** (web view models — final consumer).
5. **Operator-witnessed browser verification gate is BINDING for Sub-C end** (per Phase 7 binding convention; HTMX-driven UX cannot be verified by TestClient alone).
6. **Final integration merge after Sub-C ships green**: `git checkout main && git merge --no-ff phase7-sub-c-web -m "Merge phase7-sub-c-web into main: Phase 7 (Sub-A + Sub-B + Sub-C integrated)"`. Brings all 3 sub-dispatches' work in single merge commit. Production DB triggers 0014 migration on first `swing` invocation post-merge (backup-runner discipline applies).

**Plan-shipped status** (2026-05-04, historical): plan at `docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md` (commits `18bb35e..251cc35`; 4172 lines; 4 Codex rounds → NO_NEW_CRITICAL_MAJOR with 13 substantive findings + 2 advisory). Writing-plans dispatch brief at `docs/phase7-trade-lifecycle-state-machine-writing-plans-brief.md` (`3f7d5c1`). Plan organizes into 3 sub-dispatches (Sub-A schema/repos/state — 11 tasks; Sub-B services/CLI — 9 tasks; Sub-C web/UX — 8 tasks). Carve-out ~45 files. Total expected new fast tests: +150-250 wide band.

**Sub-A pre-conditions** (historical; SATISFIED at dispatch time):
1. ✅ Vocabulary operator-confirm (catalyst-9 / emotional_state-8 / event_type-7 — confirmed 2026-05-04).
2. ✅ Production DB backup verified to off-Drive path before migration.
3. ✅ Main at BASELINE_SHA `aa2dd60` with full fast suite green at dispatch start.
4. ✅ Marker-file Codex-blocking workflow per binding convention 2026-05-02.

**Brainstorm-shipped status:** 3 Codex rounds → NO_NEW_CRITICAL_MAJOR. Spec at `docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md` (commits `2c5fd34` initial → `c926f01` 3-round revisions). Brainstorm dispatch brief at `docs/phase7-trade-lifecycle-state-machine-brainstorm-brief.md` (`db6727d` + `9e4a761` hard-conflict-escape addition).

**Locked design decisions (from spec; do NOT relitigate at writing-plans):**
- **5-state minimal:** `entered → managing → partial_exited → closed → reviewed`. NO `planned/triggered/canceled` — `watchlist + watchlist_archive` already serves "plan and abandon." Cheap A→B expansion preserved via table-driven required-fields validator.
- **Unidirectional graph:** no `partial_exited → managing` (no pyramiding per locked constraint). Same-day stop-out = `entered → managing → closed` atomic double-transition.
- **`status` DROPPED entirely** (12 production files + 43 test files identified; full enumeration deferred to plan). 4 operation-specific predicate categories: active-trade / closed-but-not-reviewed / closed-or-reviewed / write-paths. Migration 0004 partial unique index recreated against new state predicate.
- **Fills replaces exits:** 4-action enum (`entry/trim/exit/stop`; drops `cover/add`). 1:1 backfill with `ORDER BY exit_date ASC, id ASC` deterministic ordering + 4-fixture preservation invariant test gate.
- **Aggregate denormalization on `trades`:** `current_size REAL NOT NULL`, `current_avg_cost`, `last_fill_at` — recomputed by fills-write service after every insert (single-write-path consistency).
- **`pre_trade_locked_at`:** set atomically at first `action='entry'` fill. V1 ships READ-ONLY display + audit visible; edit UI deferred to V2 (schema fully supports).
- **Premortem schema:** 3 named NULLABLE TEXT columns (technical/market_sector/execution) + 1 optional. Min-1-per-category enforced at app layer.
- **Thesis fields:** 18 KEPT + 12 DROPPED (per-field rationale in spec). All schema-NULLABLE; app-layer enforces non-empty for new entries; legacy NULL persists.
- **Pre-trade gate:** existing checks preserved + new `MissingPreTradeFieldsException` (NOT force-bypassable). Phase 9 deferred: portfolio_heat / consecutive_loss / drawdown_breaker.
- **trade_origin derivation:** 5-bucket × 4-entry-path → 4-value enum; `EntryPath` enum on `EntryRequest`; frozen-at-entry per `hypothesis_label` precedent.

**Operation-contextual validation** (added Codex R1 fix): `entry_create` enforces full required set; `transition_managing/partial_exited/closed` triggers suffice; `transition_reviewed` uses Phase 6 review-completion fields only; legacy rows exempt by NULLABLE schema.

**In-flight migration plan (verify at writing-plans dispatch):**
- VIR (closed+reviewed): `state='reviewed'`, `pre_trade_locked_at = entry_date+T16:00:00`, `trade_origin='manual_off_pipeline'` (pre-engine), 1 entry-fill + 1 exit-fill backfilled.
- DHC (open 2026-04-27, $7.58×39): `state='managing'`, `pre_trade_locked_at='2026-04-27T16:00:00'`, `trade_origin='pipeline_watch_hyp_recs'` (FIRM — operator confirmed 2026-05-04: DHC entered via Take-this-trade-equivalent on hyp-rec row with label "Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness"; bucket=`watch` confirmed empirically in candidates), 1 entry-fill, current_size=39.
- CC (open 2026-04-30, $26.97×5): `state='managing'`, `pre_trade_locked_at='2026-04-30T16:00:00'`, `trade_origin='pipeline_watch_hyp_recs'` (FIRM — phase3e-todo entry "Entry form stop-value populated incorrectly during CC entry... Take-this-trade button on hyp-recs expansion" confirms entry path), 1 entry-fill, current_size=5.
- **YOU (open 2026-05-04, $56.29×2; ADDED 2026-05-04 between writing-plans and Sub-A dispatch):** `state='managing'`, `pre_trade_locked_at='2026-05-04T16:00:00'`, `trade_origin='pipeline_aplus'` (FIRM — bucket=`aplus` confirmed in candidates table action_session 2026-05-04 + present in daily_recommendations as `today_decision`; rationale='aplus-setup' in trade_events; hypothesis_label='A+ baseline (aplus)'; operator notes "Below calculated pivot, asses pivot was aberration, went when above next highest pivot."), 1 entry-fill, current_size=2.

**Phase carve-out (~37 files; full enumeration in spec §15):** schema/data 0014.sql NEW + models.py + db.py MOD; repos trades.py MOD + fills.py NEW; services state.py NEW + entry/exit/stop_adjust/review.py MOD + origin.py NEW + derived_metrics.py NEW; web routes/trades.py + 2 view_models + 3 templates MOD; CLI MOD; journal carve-out (stats/flags/analyze/tos_import.py predicate rewrites — no schema-shape work); 4 NEW + 7 MOD test files.

**Open questions for writing-plans dispatch:**
- DHC trade_origin best-guess weak — operator may have direct recall of CLI vs web vs Take-this-trade entry path (orchestrator could not disambiguate from `trade_events.payload_json` alone; both DHC + CC have `rationale='other'`). If operator confirms otherwise, plan adjusts migration UPDATE.
- Vocabulary lists sketched (catalyst 9 / emotional_state 8 / event_type 7 values) committed as recommendations; final operator-confirm at writing-plans spec-review checkpoint.

**Estimated implementation dispatches (post-writing-plans):** 2-3 executing-plans sub-dispatches (Sub-A schema+repos+state-machine; Sub-B services+CLI; Sub-C web) + 1 verification dispatch. Total 4-6 downstream of brainstorm.

**Test count band (rough; per Phase 6 lesson "test-count-projections-bias-high"):** +150-250 fast tests (wide band; parameterization decisions affect raw count).

**Cross-references:**
- `future/swing_trading_journal_ai_ingestion_v1.2.md` §5 (state machine), §7.5 (Trade_Log), §7.6 (Fills), §10.2 (Pre-Trade Lock).
- Spec: `docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md`.
- Brainstorm brief: `docs/phase7-trade-lifecycle-state-machine-brainstorm-brief.md`.
- Existing entry-form architecture: `swing/web/view_models/trades.py` + `swing/web/routes/trades.py` (Phase 4.5 `f9a07bf`).

### Phase 8 — Daily_Management + MFE/MAE precision (gated on Phase 7)

**Bundle:** Daily_Management snapshot/event_log + per-day MFE/MAE computation via OHLCV cache + precision-flag hierarchy.

**Scope:**
- New `daily_management_records` table: `management_record_id, trade_id, record_type (daily_snapshot/event_log), review_date, current_price, current_stop, open_R_effective, portfolio_heat_contribution_dollars, MFE_to_date_R, MAE_to_date_R, thesis_status` + event_log additional fields (prior_stop, stop_changed, stop_change_reason, action_taken, emotional_state, rule_violation_suspected).
- MFE/MAE precision per v1.2 §8.6: `intraday_exact / intraday_estimated / daily_approximate`. We have OHLCV cache → daily_approximate ships immediately; intraday_estimated when intraday data sourced.
- Web dashboard tile: per-open-trade MFE/MAE-to-date.

**Estimated dispatches:** 2-3.

**Cross-references:**
- `future/swing_trading_journal_ai_ingestion_v1.2.md` §7.7 (Daily_Management), §8.6 (MFE/MAE), §10.3 (In-Trade Review workflow).
- Existing OHLCV cache: `swing/data/ohlcv_archive.py` (Phase 3 OHLCV consolidation; 696 tickers consolidated 2026-04-30).
- Existing advisory infrastructure: `swing/trades/advisory.py` (Phase 3d SMA-aware advisories) — extends naturally.

### Phase 9 — Risk_Policy entity + reconciliation depth (subsumes 2026-04-30 TOS bundle)

**Bundle:** Lift `swing.config` risk fields to versioned DB Risk_Policy entity + integrate the queued TOS-reconciliation-depth bundle (close-fill price mismatch + stop-order reconciliation + position-qty reconciliation) into a structured Reconciliation_Run / Reconciliation_Discrepancy framework.

**Scope:**
- New `risk_policy` table: `policy_id, effective_from, effective_to, is_active, max_account_risk_per_trade_pct, max_concurrent_positions, max_portfolio_heat_pct, max_sector_concentration_positions, consecutive_losses_pause_threshold, drawdown_circuit_breaker_enabled` (default false). Existing `swing.config.toml` values become the seed of policy_id=1.
- New `reconciliation_runs` + `reconciliation_discrepancies` tables. Existing `tos_import` reconcile flow refactors to write Reconciliation_Run rows + Discrepancy rows for each mismatch (close-price, stop, position-qty, cash). Material-to-review semantics: discrepancies on reviewed trades reopen the review.
- Subsumes the standalone "2026-04-30 TOS reconciliation depth follow-ups (BUNDLED)" entry above — when Phase 9 ships, the queued bundle's three gaps (close-price + stop + position-qty) ship as part of Phase 9, not as a separate dispatch.

**Estimated dispatches:** 3-4.

**Cross-references:**
- `future/swing_trading_journal_ai_ingestion_v1.2.md` §7.8 (Risk_Policy), §7.9 (Reconciliation_Log), §10.5 (Reconciliation Workflow).
- This document's "2026-04-30 TOS reconciliation depth follow-ups (BUNDLED)" entry above.
- Existing config: `swing/config.py` + `swing.config.toml`.
- Existing TOS import: `swing/journal/tos_import.py`.

### Sequencing alternatives (for future re-evaluation):

- **(A) Phase 6 only, defer 7-9 indefinitely.** Operator stops journal extension at the cheapest piece. Acceptable if Phase 6 turns out sufficient.
- **(B) Phase 6 + 9, defer 7 + 8.** "Journal Lite" — post-trade review + risk policy + reconciliation depth. Skips state-machine + Daily_Management.
- **(C) Full sequence 6 → 7 → 8 → 9.** Multi-month commitment to full v1.2 equivalence.
- **(D) Defer all of v1.2 until first hypothesis closure.** Per orchestrator-context lesson: "the actually-urgent next move is operational — take hypothesis-tagged trades, accumulate evidence." If journal-discipline-measurement isn't bottlenecking the loop today, defer engagement until a hypothesis closes and "did the framework work?" requires deeper retrospective tooling.

Recommendation: **(A) ship Phase 6, then re-evaluate.** Re-evaluation criteria: does Phase 6's post-trade review surface produce the structured behavioral data the operator wants? If yes + state-machine discipline becomes a real bottleneck (e.g., partial_exited tracking matters for evidence aggregation), proceed to 7. If no, hold at Phase 6.

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

## 2026-05-04 Finviz Elite API integration (QUEUED; Medium effort; brainstorm needed)

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

1. **Library choice: Schwabdev vs build-from-scratch.** Schwabdev (https://github.com/tylerebowers/Schwabdev) wraps the entire Schwab Trader API surface (auth, account, orders, market data, streamer); reviewing time-to-first-working-Phase-A is faster with the wrapper. Risks: unofficial → Schwab API changes can break it; maintainer-bus-factor (single-author project); supply-chain trust (vendor + pin to specific commit/version, OR vendor the source into `swing/integrations/schwab/_vendor/`). Recommendation: adopt Schwabdev for V1 with a vendored / version-pinned dependency + thin abstraction layer (`swing/integrations/schwab/client.py`) so swap-to-direct-API is bounded if the wrapper goes stale. Confirm at brainstorm time.
2. **Phase A vs Phase B vs Phase C ordering — operator preference.** Recommendation: A (account reconciliation) → B (data source) → C (trade automation). A is cheapest; B has highest yfinance-pain-relief value; C is highest-risk + lowest urgency at $7,500 capital with 1-2 trades/month pace.
3. **OAuth refresh-token storage location.** User-config TOML (per Phase 5)? New encrypted store? Operator's risk preference.
4. **Schwab Developer Portal production-access approval time.** Could be days to weeks; orchestrator-blocking for Phase A start.
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

---

## 2026-05-04 Worktree cleanup script: pytest-of-rwsmy ACL-lock pattern recurrence check (TRIGGER-GATED)

**Trigger:** AFTER Phase 7 ships (all 3 sub-dispatches A/B/C merged to main). At that point, attempt to cleanup `.worktrees/phase7-sub-a-schema/`, `.worktrees/phase7-sub-b-services/`, `.worktrees/phase7-sub-c-web/`. If any of them surface the same `.tmp/pytest-of-rwsmy/` ACL-lock pattern that Phase 5 + Phase 6 hit, the issue is durable across phases and the cleanup script needs a permanent extension.

**Background.** Phase 5's `.worktrees/phase5-config-page-redispatch/` and Phase 6's `.worktrees/phase6-post-trade-review/` both left orphaned on-disk directories after `git worktree remove` failed with `Permission denied on .tmp/pytest-of-rwsmy/` — Windows ACL inheritance from the pytest subprocess's tmp dir. The 2026-05-02 `cleanup-locked-scratch-dirs.ps1` extension added Codex-sandbox naming patterns but does NOT match `pytest-of-rwsmy/`. Phase 6 cleanup attempt 2026-05-04 (`takeown /F ... /R /D Y` + `icacls ... /reset /T /C /Q` + `Remove-Item -Recurse -Force`) succeeded on 1196/1198 files but 2 files in `.tmp/pytest-of-rwsmy/` remained ACL-locked.

**Why deferred to post-Phase-7:** Phase 7 has 3 worktrees (Sub-A/B/C). After all 3 ship, we have 5 data points (Phases 4 + 5 + 6 + Phase 7 sub-dispatches) on whether this is recurring. If Sub-A/B/C all hit it, the pattern is durable + the cleanup script needs the extension. If only some hit it, the pattern correlates with something other than just Windows ACL inheritance (test runner state? subagent isolation?) and a deeper investigation is warranted before the script extension.

**V1 scope (when triggered):**
1. Document the recurrence count post-Phase-7 (how many of A/B/C hit the lock; commands attempted; success rate per cleanup approach).
2. Extend `cleanup-locked-scratch-dirs.ps1` to handle `.tmp/pytest-of-rwsmy/**` patterns: ownership transfer + ACL reset + retry-with-elevation if still locked.
3. Add a corresponding gotcha entry to CLAUDE.md (Windows-section): pytest tmp-dir ACL-inheritance breaking worktree cleanup.
4. Verify the script handles all 3 Phase 7 sub-dispatch worktrees in actual mode (not just DryRun).

**Out-of-scope:**
- Modifying pytest's tmp-dir creation behavior (upstream concern; would need pytest config change).
- Eliminating the `.tmp` dir creation in worktrees entirely (pytest needs it for parallel-test scratch).
- Investigating WHY Windows ACL inheritance produces immutable subdirs (deep Windows-internals work; not productive).

**Cross-references:**
- `docs/orchestrator-context.md` §"Active orchestrator-side housekeeping" — Phase 6 cleanup state recorded.
- `cleanup-locked-scratch-dirs.ps1` (project root) — current script; needs `.tmp/pytest-of-rwsmy/` pattern addition.
- Phase 5 cleanup pattern recurrence (orchestrator-context lessons captured 2026-05-02).
- Phase 6 cleanup partial-success record (orchestrator-context "Active orchestrator-side housekeeping" 2026-05-04).

---

## 2026-05-04 Handoff document growth — structural separation + retention discipline (QUEUED; tripwire-gated)

Operator-surfaced 2026-05-04 during Phase 7 brainstorm dispatch prep. The fresh-orchestrator handoff pattern (start a new conversation instance before each major iteration to minimize accumulated tool-result noise) loses leverage as the persisted handoff documents themselves grow.

### Problem

`docs/orchestrator-context.md` (~71k tokens) and `docs/phase3e-todo.md` (~65k tokens) accrete monotonically — lessons captured, recent decisions, in-flight prose, SHIPPED items. Fresh-orchestrator bootstrap currently consumes ~200-250k tokens to load context (the two accreting docs + `CLAUDE.md` + system prompt + initial `git status`/`git log`). Growth rate ~30-50k tokens/phase. Beyond a threshold, bootstrap consumes enough of the working window that the savings vs continuing a long conversation are largely defeated.

### Trigger

Fire the project when total bootstrap consumption (after a fresh orchestrator reads `docs/orchestrator-context.md` + `docs/phase3e-todo.md` + `CLAUDE.md` + runs `git status` + `git log --oneline -20`) exceeds **300k tokens** (~30% of Opus 1M window). Measured by the orchestrator's reported context utilization after standard bootstrap (e.g., `/cost` or equivalent context-check). Below threshold: bank the observation, defer.

Operator-paced verification: any fresh orchestrator can sanity-check bootstrap consumption against this trigger; if exceeded, surface to operator as project-readiness signal.

### Recommended approach (subject to re-evaluation when triggered)

1. **Structural separation (one-time refactor; dominant cost).** Split each accreting doc into `*-active` + `*-archive`:
   - `orchestrator-context-active.md` (current state, immediate next moves, currently-binding framings — capped) + `orchestrator-context-archive.md` (historical narrative, older captured lessons, superseded decisions).
   - `phase3e-todo-active.md` (open backlog) + `phase3e-todo-archive.md` (SHIPPED items + closed entries).
   - Bootstrap discipline: fresh orchestrator reads only `-active` files; archive is searchable on demand via grep / Read.
2. **Light retention discipline (ongoing; minor curation cost).**
   - SHIPPED items in `phase3e-todo.md` move to archive when the next phase ships (one-phase cooldown).
   - "Lessons captured" caps at last ~30 entries; older lessons promote to `CLAUDE.md` (when durable code-failure prevention) or archive (when process-only).
   - "Recent decisions and framings" entries that have been superseded migrate to archive.

### Out-of-scope alternatives considered

- Pure compression (replace prose with terse cross-refs to per-phase briefs) — sacrifices "everything in one file" without structural clarity benefit.
- Bootstrap-discipline change alone (cap reading without splitting) — discipline-failure risk; silent recurrence.
- Tooling-based auto-summary script (regenerate snapshot from git log + DB) — premature; structural separation is simpler and lower-maintenance.

### Estimated effort

1 dispatch — one-time refactor (split docs, write the cross-reference scaffolding, populate active vs archive) + write the retention-discipline rules into `orchestrator-context-active.md` as a maintenance section. Probably writing-plans-skip viable; copowers:executing-plans direct.

### Cross-references

- `docs/orchestrator-context.md` §"Lessons captured" + §"Currently in-flight work" (especially the per-phase prose paragraphs) + §"Recent decisions and framings" — three highest-velocity growth surfaces.
- `docs/phase3e-todo.md` — entire file; SHIPPED items 3e.1 / 3e.3 / 3e.4 / 3e.5 (2026-04-26) still inline a week later, illustrating the cooldown-archival opportunity.
- This entry's tripwire mechanism is itself a precedent for trigger-gated backlog items (vs always-active or operator-paced-deferred). If useful, document the pattern in `orchestrator-context.md` after first activation.
