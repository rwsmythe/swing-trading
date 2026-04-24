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
