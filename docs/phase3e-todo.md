# Phase 3e — Known Gaps & Follow-ups

Backlog captured at the end of the Phase 3d walkthrough. Not a commitment, just
a trackable list. Prioritize before starting a Phase 3e spec cycle.

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
- **Sizing-hint hx-trigger parsing bug (pre-existing behavioral degradation).** Current trigger string in `partials/trade_entry_form.html.j2` (sizing-hint span): `change from:input[name=entry_price],input[name=initial_stop] delay:200ms`. Per HTMX 2.0.3's tokenizer, this parses as TWO separate triggers because HTMX splits on top-level commas: (1) `change` event from `input[name=entry_price]` with NO delay (delay:200ms attaches to the second trigger only); (2) `input` event with broken filter expression `[name=initial_stop]` which compiles into `event.name = (event.initial_stop ?? window.initial_stop)` — always evaluates undefined → never fires. Net effect: sizing-hint fires correctly on entry_price changes (without intended debounce) but NEVER fires on initial_stop changes. **Recommendation:** likely fix is HTMX's parens-grouped from-selector syntax: `change from:(input[name=entry_price],input[name=initial_stop]) delay:200ms`. Verify against HTMX 2.0.3 behavior (test in browser; check HTMX docs). ~30 min including a smoke test that asserts both fields trigger sizing-hint requests with debounce. Behavioral degradation; affects sizing feedback UX but not correctness.

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

---

## 2026-04-26 chart-pattern flag-v1 brainstorm follow-ups

Items surfaced during the chart-pattern flag-v1 brainstorm dispatch (commit chain `9583f19..081f689`, spec at `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`, 5 adversarial Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`). Implementation queued via writing-plans dispatch; these items are explicitly out of V1 scope.

### V2+ pattern coverage (deferred per locked-constraint #1):

- **Pennant pattern.** Same shape geometry as flag but with converging trendlines. V2 adds to `pattern` IN-list via new migration; classifier adds geometric gates for trendline convergence.
- **Cup-with-handle pattern.** Multi-month U-shape + shallow pullback near pivot. Larger geometric definition surface; likely benefits from multi-timeframe consideration.
- **Flat base pattern.** ≥5 weeks, range ≤~15%. Simpler than flag; mostly range-CV + duration check.
- **Tight channel pattern.** 2+ weeks of converging highs/lows. Variant of flag with stricter parallel-line geometry.
- **Qullamaggie taxonomy patterns.** episodic_pivot, power_earnings_gap, parabolic_short, gap_and_go, base_breakout, ipo_breakout — all available as reference layer via the qullamaggie MCP; some require external context (earnings calendar, IPO date) and are not pure-shape classifications.

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
