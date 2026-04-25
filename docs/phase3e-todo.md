# Phase 3e — Known Gaps & Follow-ups

Backlog captured at the end of the Phase 3d walkthrough. Not a commitment, just
a trackable list. Prioritize before starting a Phase 3e spec cycle.

---

## Dashboard / UX enhancements

### 3e.1 — Mark-to-market on Account card

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

### 3e.3 — `POST /prices/refresh` also clears OHLCV breaker

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

### 3e.4 — Watchlist entries can expand but cannot collapse

**Observed:** Clicking a watchlist row expands it to show details. Clicking the
expanded row does nothing — no toggle/collapse. Operator has to refresh the
page to reset the view.

**Proposed:** Make the expand trigger a toggle (click again to collapse), OR
add an explicit collapse affordance (close X in the expanded panel).

**Scope:** 1 template + HTMX swap pattern change. Phase 2 untouched.

---

### 3e.5 — Stale placeholder text in expanded watchlist entries

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

### 3e.6 — No graph pattern shape estimation

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

**Reference pattern images already in repo:**
- `reference/flag_pattern.png`
- `reference/pennant_pattern.png`
- `reference/tight_channel_flat_base.png`

---

## Summary

| ID | Area | Complexity | Phase 2 carve-out? |
|---|---|---|---|
| 3e.1 | Unrealized P&L on Account card | Low | No |
| 3e.2 | Partial-exit realized in journal total | Low | No |
| 3e.3 | Prices-refresh clears OHLCV breaker | Low | No |
| 3e.4 | Watchlist collapse toggle | Low | No |
| 3e.5 | Remove stale "Log entry" placeholder | Trivial | No |
| 3e.6 | Chart pattern shape estimation | High | Probably yes |

3e.1–3e.5 are all small and could land as a single Phase 3e batch (~2–3 days
of work). 3e.6 is a standalone Phase 3f candidate.

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
