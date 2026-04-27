# Chart-Pattern Flag-V1 — Manual Verification Results

**Round date:** 2026-04-27
**Run by:** operator (Reid Smythe), guided step-by-step by orchestrator
**Procedure followed:** `docs/chart-pattern-flag-v1-manual-verification.md`
**Coverage:** ~75% (full verification of paths exercisable with current data; flag-classification-dependent paths deferred since 0 flag classifications exist in cache; additional-trade-dependent paths deferred to natural future workflow)

**Headline result:** V1 chart-pattern surfaces work as designed, with ONE confirmed production regression (mathtext title fix) and several open design questions surfaced for post-V1 triage. Phase 5 ToCToU snapshot pattern verified end-to-end via real trade entry (DHC, 2026-04-27).

---

## Coverage table

| Section | Status | Notes |
|---|---|---|
| §0 Pre-flight | ✅ | Schema=10, run 24 has 5 classifications all `pattern='none'`, 0 flags |
| §1.1 Account card + Open positions | ✅ | Unrealized P&L line item conditional on having open position; verified post-DHC entry |
| §1.2 Watchlist top-5 | ✅ | No flag tags expected (correct); sort-neutrality verified |
| §1.3 Expand watchlist row | ✅ | Chart inline for chart-scope tickers; "Chart unavailable" for out-of-scope |
| §1.4 Refresh-now (Bug 1 layout) | ✅ | Layout regression durably fixed |
| §2 Standalone /watchlist | ✅ | 31 rows; no flag tags; first-5 match dashboard order |
| §3.1 Chart title (mathtext) | **❌ REGRESSION** | Title shows `pivot 72.97stop40.69` with "stop" italicized — `\$` fix in commit `2fd0ecc` does NOT prevent math mode entry |
| §3.2 Chart overlay (flag pattern) | Deferred | No flag classifications in cache to render against |
| §3.3 Non-flag chart (no overlay) | ✅ | No bands/algo-pivot painted; candidate-pivot + stop hlines preserved |
| §3.4 Classifier-error chart | Deferred | No classifier-error rows in current data |
| §4.1 Form Chart Pattern section | ✅ | DHC: `none` + computed timestamp + Accept-algo default + override dropdown displayed |
| §4.2 Submit Accept-algo, snapshot persisted | ✅ | DHC trade row #2 persisted `(algo='none', confidence=None, operator=None, anchor=24)` |
| §4.3 Override = "flag" | Deferred | Requires additional real trade |
| §4.4 Override = "none" | Deferred | Requires additional real trade |
| §4.5 Override = "other" + free text | Deferred | Requires additional real trade |
| §4.6 Not classified stub (out-of-scope) | ✅ | ELVN form: stub message exact; no override surface |
| §4.7 Soft-warn × chart_pattern | Deferred | Requires 4+ open trades to fire SoftWarnException |
| §5.1 CLI WITH cached classification | Deferred | Requires additional real trade |
| §5.2 CLI refusal gate | ✅ | ELVN: exit 1; spec §3.7-verbatim error message; no trade row created |
| §5.3 CLI without --chart-pattern-operator | Deferred | Backward-compat verification requires real trade |
| §6 Cross-surface consistency | Partial | Verified for `pattern='none'` (all surfaces agree); full requires flag detection |

---

## Production bugs found (action items)

### #1 — Mathtext title fix regression (REGRESSION introduced 2026-04-27 commit `2fd0ecc`)

**Severity:** V1 cosmetic; visible on every chart.
**Symptom:** AMKR chart title renders as `AMKR | pivot 72.97stop40.69 | last 120 bars` — `$` signs stripped, "stop" italicized, spaces between `72.97`/`stop`/`40.69` collapsed.
**Root cause:** matplotlib's `\$` escape doesn't prevent math mode entry. Behavior:
- Source string: `f"{ticker} | pivot \\${pivot:.2f} stop \\${stop:.2f} | last {len(df)} bars"` (raw f-string with `\$`)
- matplotlib renders `\$` as literal `$` BEFORE math-mode parsing
- Resulting effective string: `... pivot $72.97 stop $40.69 ...`
- Paired `$..$` triggers math mode → "stop" italic, spaces collapsed, `$` consumed

**Tests passed but visual was never re-verified after the fix landed.** Original commit message claimed "Verified by tests/rendering/test_chart_overlay.py (7 passed)" — those tests assert on title STRING (`r"AAPL | pivot \$110.00 stop \$95.00 ..."`), not on rendered PNG output. **This violated the Phase 6 lesson "Manual visual verification is not optional for rendering work."**

**Real fix options:**
- **(a) Remove `$` from title format** (simplest, one-line). Title becomes `pivot 72.97 stop 40.69` — trading context already implies dollars.
- **(b) `fig.suptitle(..., parse_math=False)`** after `mpf.plot(returnfig=True)`. Disables math-mode parsing entirely on the suptitle. Requires touching the rendering code path.
- **(c) Use `$` (Unicode escape for $)** — likely renders as literal $ without math mode, but unverified.

**Recommended:** (a) for simplicity. Update tests to expect new title format. Manually re-verify rendered PNG before committing.

**Files:** `swing/rendering/charts.py:86`, `tests/rendering/test_chart_overlay.py:270` and `:287`.

---

### #2 — No standalone chart-image route

**Severity:** V1 UX gap.
**Symptom:** `http://127.0.0.1:8080/charts/<TICKER>.png` returns 404. Charts only served via the expanded-watchlist-row HTMX partial.
**Impact:** Operator can't view a chart for a ticker that's not in watchlist (e.g., open positions, post-trade-entry tickers).
**Real fix:** Add a route handler in `swing/web/routes/charts.py` (or wherever chart serving lives) that serves PNG files from `exports/<session>/charts/`. Route pattern: `/charts/<ticker>.png` returns 404 if no chart exists for the ticker in the latest pipeline run.

---

### #3 — Open positions table rows don't expand to charts

**Severity:** V1 UX gap.
**Symptom:** After entering a trade, the ticker moves from active watchlist to open positions. The watchlist row's expand-to-chart pattern doesn't apply to open positions table rows. Operator loses easy chart-view path.
**Impact:** During trade management (stop adjustment, exit decisions), operator can't quickly view the chart from the dashboard.
**Real fix options:**
- (a) Add expand-to-chart affordance on open-positions rows (HTMX-swap to chart partial).
- (b) Add "View chart" button in Actions column.
- (c) Implement #2 standalone route + link from open-positions row to `/charts/<ticker>.png`.

**Related:** ties to #2.

---

### #4 — Chart-scope set selection misaligned with Phase 4 watchlist sort

**Severity:** Substantive — likely contributing to zero flag detections.
**Symptom:** Chart-scope set (5 tickers per pipeline run) does NOT align with the dashboard's top-5 watchlist by display priority.
**Empirical evidence (from this verification round):**
- Dashboard top-5 watchlist (Phase 4 tag-aware composite sort): DHC, TWST, GFS, ALTO, RNG
- Chart-scope set (run 24): AMKR, CC, DHC, PLAB, PUMP
- Only DHC overlaps. Other 4 watchlist top-5 (TWST/GFS/ALTO/RNG) get NO classification.
- Other 4 chart-scope tickers (AMKR/CC/PLAB/PUMP) sit mid-watchlist (positions ~6-15ish).
- "Chart unavailable" message wording confirms: `"this ticker isn't in today's charting scope (A+ names + top near-trigger watchlist)"` — "near-trigger" is proximity-based, NOT tag-aware.

**Why it matters:** chart-scope determines which tickers get pattern classifications. Tickers that the operator's primary attention surface (watchlist top-5) prioritizes may not get flag-pattern detection — directly limiting the system's ability to surface flag patterns at all.

**Hypothesis:** aligning chart-scope with the watchlist's tag-aware composite sort would put algorithmically-priority tickers in the classification pool, possibly surfacing flag patterns the system currently misses.

**Investigation target:** chart-scope resolver. Likely in `swing/web/chart_scope.py` or pipeline step that builds chart targets.

**Caveat:** changing chart-scope selection could affect chart generation costs (yfinance OHLCV fetches) and may shift what the operator sees in expanded watchlist rows. Needs operator-aligned design before implementation.

---

## Open design questions (operator decisions needed)

### #5 — Lightning icon trigger logic re-evaluation

**Current logic (per `swing/web/templates/partials/watchlist_row.html.j2:7`):**
```jinja
{% if price and w.entry_target and price.price >= w.entry_target * 0.99 %}⚡{% endif %}
```

**Translation:** fires when current price is within 1% of entry target or above (`price >= 0.99 × entry_target`).

**Operator concern:** post-Phase-4 (with richer tag tier + pattern classification + hypothesis-recommendation engine), the simple "near pivot" indicator may not be the right "actionability" signal anymore.

**Options:**
- Keep as-is.
- Distinguish "approaching" (-1% to 0%) from "triggered" (>0%) with different icons/colors.
- Tighten threshold (e.g., ±0.5%).
- Tag-aware tiering (only fire on A+ within range; or scale icon weight by tag count).
- Pattern-aware combination (fire only when also has flag classification within range).

---

### #6 — Multiple concurrent advisories vs single price-stop field

**Symptom:** Open positions advisory column shows multiple concurrent trail-stop advisories (e.g., DHC: 10MA-based $7.23 + 20MA-based $7.06). Trade row stop is a single price field.

**Reconciliation questions:**
- Does adjusting the stop to satisfy ONE advisory clear the other?
- Does adjusting to the more conservative value (lower of the two) clear both?
- Is the operator expected to choose ONE advisory to follow?

**Investigation:** Phase 3d advisory expiry logic. May need to clarify operator intent before deciding state-machine.

---

## Verification doc fixes needed

(Apply as a single doc-fix commit when convenient — none are blocking.)

7. **§0 SQL queries** assume `sqlite3` CLI on PATH. Add Python-equivalent forms (sqlite3 module is in Python stdlib; works without separate install).
8. **§0.2 SQL "error" column** conflates LEFT-JOIN-NULL (no classification row exists for that pipeline run) with classifier-error rows (`pattern IS NULL AND ticker IS NOT NULL`). Fix: `SUM(CASE WHEN ppc.pattern IS NULL AND ppc.ticker IS NOT NULL THEN 1 ELSE 0 END)`.
9. **Python equivalents for PowerShell** need single-line invocations or temp-script files. Triple-quoted strings in `python -c "..."` get mangled by PowerShell's quote handling.
10. **§1.1.a Unrealized P&L check** should be marked "conditional on having open positions" — line item legitimately doesn't render with zero positions.
11. **§1.1 Account card breakdown** doc mentions Starting equity / Realized P&L / Net cash separately; actual display is compact `$<equity> + <count>/<cap> + Unrealized: $X.XX`. Either dashboard has been simplified vs doc OR doc overstates expectations. Reconcile by inspecting current dashboard template.
12. **§3 chart-image instructions** assume ticker stays in watchlist post-trade-entry. Doesn't account for open-position case. Should suggest direct URL fallback (once #2 ships) OR list of non-traded chart-scope tickers.
13. **§5.2 CLI command** had wrong option names + missing required options:
    - `--entry` → `--entry-price`
    - `--stop` → `--initial-stop`
    - Missing required: `--entry-date YYYY-MM-DD`, `--shares <int>`
    - `--rationale` is `click.Choice([aplus-setup, near-trigger-breakout, vcp-breakout, pivot-breakout, post-earnings-continuation, relative-strength, other])` — free-text rejected
    - For `--rationale other`, `--notes` is required.
    - Working command: `swing trade entry --ticker ELVN --entry-date 2026-04-27 --entry-price 45.13 --shares 1 --initial-stop 29.37 --rationale other --notes "manual test for refusal gate" --chart-pattern-operator flag`
14. **Chart's purple dotted vertical line** ("consolidation marker" per Phase 6 retro) lacks operator-facing legend/tooltip OR doc explainer. Operator queried "what is this?" — answer not surfaced anywhere user-visible.

---

## Walkthrough chronological log (key data points)

- **§0 baseline:** Schema 10. Pipeline run 24 (latest, `finished_ts=2026-04-26T23:04:18`) has 5 classifications all `none`. Run 23 same. Older runs (20-22) have no classification rows. **Zero flag classifications anywhere in cache.**
- **§0.3 chart-scope tickers run 24:** AMKR, CC, DHC, PLAB, PUMP (all `pattern='none'`).
- **§1.1 Account card:** initially `$1298 + 0/4 (hard cap 6)`; after DHC trade entry, line gained `Unrealized: $3.12`.
- **§1.2 watchlist top-5:** DHC ⚡, TWST, GFS, ALTO ⚡, RNG. All TT✓ tags only. Lightning fires on DHC + ALTO (within 1% of pivot). 31 total active watchlist entries.
- **§2.1 standalone watchlist:** confirmed mid-list lightning hits include AMKR, PUMP, CC, PLAB, DFTX (all within 1% of pivot). All "(stale)" prices (cache age).
- **DHC trade entered 2026-04-27** via web form. Trade row #2: `(2, 'DHC', 'none', None, None, 24)`. Spec §3.6 ToCToU snapshot persisted AS-IS.
- **§3.1 mathtext bug observed on AMKR chart** post trade entry (DHC chart no longer accessible — open positions don't expand).
- **§4.6 "Not classified" stub** on ELVN form — exact wording, no override surface.
- **§5.2 CLI refusal gate** on ELVN — exit code 1, spec §3.7 verbatim error message: `--chart-pattern-operator requires a cached classification for ELVN; ticker is out-of-scope for the latest pipeline run. (V1 cached-only; manual fallback deferred to V2.)`

---

## Recommended action priority

**Tier 1 — V1-quality fixes (land before Task 7.3 fixture labeling):**

- #1 mathtext title regression (small fix; I introduced it; prevents legible chart titles during operator labeling work)

**Tier 2 — Operator-workflow improvements:**

- #2 + #3 chart-view UX (direct route + open-positions expand) — improves trade-management workflow
- #4 chart-scope set alignment with Phase 4 watchlist sort — substantive; may unlock more flag detections; investigation + design discussion required first

**Tier 3 — Design discussions (operator decisions):**

- #5 lightning icon redesign (operator decision)
- #6 advisory state-machine vs single price stop (operator decision; Phase 3d follow-up)

**Tier 4 — Verification doc cleanup:**

- #7-13 — bundle into single doc-fix commit
- #14 chart legend / consolidation marker explainer (small)

**Verification deferred until operator workflow naturally exercises:**

- §3.2 (chart overlay flag-painting) — needs flag classifications. Currently zero. Once chart-scope alignment (#4) lands AND/OR market produces flag patterns in current chart-scope, retest.
- §3.4 (classifier-error chart) — needs error rows. Currently zero.
- §4.3-4.5 (override variants on real trades) — exercise at next 2-3 trade entries.
- §4.7 (soft-warn × chart_pattern) — needs 4+ open trades. Defer to natural workflow.
- §5.1 (CLI WITH cached classification) — exercise at next trade taken via CLI.
- §5.3 (CLI without --chart-pattern-operator backward-compat) — exercise at next CLI trade entry.
- §6 (full cross-surface consistency) — needs `pattern='flag'` ticker.

---

## Process notes for next orchestrator

- Operator's discipline during walkthrough: "do not take action on feedback until we finish or hit a significant blocker." All findings collected as observations; nothing fixed mid-walkthrough except absolutely-blocking logistics (e.g., sqlite3 CLI not on PATH → switched to Python equivalents inline).
- Mathtext regression #1 is the only "definitely needs fixing" production item; everything else is design discussion, doc cleanup, or expected-blocked.
- The verification doc itself (`docs/chart-pattern-flag-v1-manual-verification.md`) needs material updates per items #7-14 — recommend bundling those fixes when addressing #1 OR as a separate small commit when the verification doc is next consulted.
- Phase 7 implementer-side ship + this verification round establishes V1 functional baseline. Task 7.3 (operator-labeled fixtures) and Task 7.4 (FP-biased tuning) are the remaining V1-ship gates. Operator paced; not orchestrator-bottlenecked.
