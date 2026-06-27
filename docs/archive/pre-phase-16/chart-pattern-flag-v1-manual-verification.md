# Chart-Pattern Flag-V1 — Manual Verification Procedure

**Purpose:** Step-by-step procedure for the operator to manually verify chart-pattern flag-v1 displays correctly across web + CLI surfaces after Phase 6 (build phases complete) + Phase 7 implementer-side (test infrastructure) ship.

**When to run:** After Phase 7 implementer-side dispatch ships Tasks 7.1 + 7.2; ideally BEFORE operator begins Task 7.3 fixture labeling work (so any UI bugs surface before they affect labeling efficiency).

**Expected duration:** ~30-45 minutes for a thorough walkthrough.

**Prerequisites:**
- swing-trading repo at HEAD with Phase 7 implementer-side shipped (or at minimum Phase 6 complete + mathtext title fix `29c93f5` landed; commit `2fd0ecc` was a failed earlier attempt — see `docs/chart-pattern-flag-v1-manual-verification-results.md` §#1).
- Production DB at `~/swing-data/swing.db` with schema_version = 10.
- A recent pipeline run with classifications populated in `pipeline_pattern_classifications` table.
- `swing` CLI on PATH (`%APPDATA%\Python\Python314\Scripts\` per CLAUDE.md).

---

## §0 Pre-flight checks

Before walking through the surfaces, confirm baseline state.

**Note on running SQL queries:** The blocks below use the `sqlite3` CLI for readability. If `sqlite3` isn't on your PATH (default Windows install rarely has it), use Python's stdlib `sqlite3` module instead — it ships with every Python install.

```bash
# Python stdlib equivalent — works without sqlite3 CLI on PATH (gitbash):
python -c "
import sqlite3, os
conn = sqlite3.connect(os.path.expanduser('~/swing-data/swing.db'))
for row in conn.execute('SELECT version FROM schema_version'):
    print(row)
"
```

PowerShell users: `python -c "..."` mangles triple-quoted multi-line SQL through PowerShell's quoting. Easiest workaround — write a temp `.py` file:

```powershell
@'
import sqlite3, os
conn = sqlite3.connect(os.path.expanduser("~/swing-data/swing.db"))
for row in conn.execute("SELECT version FROM schema_version"):
    print(row)
'@ | Out-File -Encoding utf8 _query.py; python _query.py; Remove-Item _query.py
```

Adapt the cursor query body for each SQL block in the rest of this doc.

```bash
# 1. Schema version is 10 (Phase 2 migrations 0009 + 0010 applied)
sqlite3 ~/swing-data/swing.db "SELECT version FROM schema_version"
# Expected: 10
```

```bash
# 2. Recent pipeline run exists with classifications populated
sqlite3 ~/swing-data/swing.db "
  SELECT
    pr.id AS pipeline_run_id,
    pr.evaluation_run_id,
    pr.state,
    pr.finished_ts,
    COUNT(ppc.ticker) AS classification_count,
    SUM(CASE WHEN ppc.pattern = 'flag' THEN 1 ELSE 0 END) AS flag_detected_count,
    SUM(CASE WHEN ppc.pattern = 'none' THEN 1 ELSE 0 END) AS no_flag_count,
    SUM(CASE WHEN ppc.pattern IS NULL AND ppc.ticker IS NOT NULL THEN 1 ELSE 0 END) AS classifier_error_count
  FROM pipeline_runs pr
  LEFT JOIN pipeline_pattern_classifications ppc ON ppc.pipeline_run_id = pr.id
  WHERE pr.state = 'complete'
  GROUP BY pr.id
  ORDER BY pr.finished_ts DESC
  LIMIT 5"
# NOTE: classifier_error_count requires `AND ppc.ticker IS NOT NULL` — without it,
# a LEFT-JOIN-NULL row (no classification was ever attempted for this pipeline_run)
# is conflated with a true classifier-error row (ppc row exists, pattern is NULL).
```

**Expected output:** at least one row showing `state='complete'` and `classification_count > 0`. Note the `pipeline_run_id` and any tickers with `pattern='flag'` for the per-ticker steps below.

If `classification_count = 0` or no recent pipeline run: trigger a fresh run via the dashboard's "Run pipeline" button OR `swing pipeline run`. Wait for completion (~1-3 min for chart-scope tickers) before proceeding.

```bash
# 3. Confirm at least one ticker has a 'flag' classification (needed for overlay verification)
sqlite3 ~/swing-data/swing.db "
  SELECT pipeline_run_id, ticker, pattern, confidence, pivot
  FROM pipeline_pattern_classifications
  WHERE pattern = 'flag'
  ORDER BY pipeline_run_id DESC, confidence DESC
  LIMIT 5"
```

**Expected output:** at least one ticker with `pattern='flag'`. If empty: the current data window doesn't have any flag patterns; that's fine for some checks but blocks the overlay verification (§3) and trade-entry-form-with-classification verification (§4). Either wait for a fresh pipeline that detects a flag, OR proceed with checks that don't require a flag-tagged ticker (§1, §2 partial, §5 partial).

---

## §1 Web surface — Dashboard

```bash
# Start the web server
swing web
```

Open `http://127.0.0.1:8080/` in browser.

### §1.1 Account card + Open positions
- [ ] **Account card** displays compact form: `$<equity> + <open_count>/<concurrent_cap> (hard cap <hard_cap>)` (e.g., `$1298 + 0/4 (hard cap 6)`).
- [ ] **Unrealized P&L line item** — appears as `Unrealized: $X.XX` **only when at least one open position exists** (Phase 3e.1; shipped pre-V1). With ZERO open positions, the line legitimately does NOT render — this is correct behavior, not a regression. Skip this check if no open positions.
- [ ] **Open positions** table renders without 500 errors. If you have open trades, they appear; if zero open trades, the table renders empty or is omitted depending on template state.

### §1.2 Watchlist top-5
- [ ] Watchlist top-5 section heading "Watchlist - near trigger" appears (Bug 1 from Bugs.txt — fixed pre-V1).
- [ ] Top-5 table renders 5 rows (or fewer if active watchlist has < 5 entries).
- [ ] **Pattern tag rendering** — for any ticker that has a `pattern='flag'` classification AND `confidence >= cfg.web.flag_pattern_display_threshold` (default 0.0, so all flag detections show by default):
  - [ ] Tags cell displays `flag (0.78)` (or whatever the actual confidence is) **alongside** existing `TT✓`, `VCP✓`, `A+` tags.
  - [ ] Format: `TT✓ · VCP✓ · A+ · flag (0.78)` — middle-dot separator between tags.
- [ ] **Sort order unchanged from pre-V1.** Watchlist sort key is still tag-count → tag-precedence → proximity → ticker (per Phase 4 sort-neutrality structural guarantee). The flag tag does NOT participate in sort. Eyeball: tickers with more `TT✓ VCP✓ A+` tags should sort higher; flag tag presence shouldn't change order.
- [ ] **Show all (N)** link works; navigates to `/watchlist`.

### §1.3 Click into expanded watchlist row
- [ ] Click a row to expand (HTMX swap).
- [ ] Expanded row shows ticker details + **chart image** (if ticker has a chart in the chart-scope set — A+ + top near-trigger watchlist).
- [ ] **Close button** at top-right of expanded row collapses it (Phase 3e.4; shipped pre-V1).
- [ ] **Stale "Log entry" placeholder REMOVED** (Phase 3e.5; shipped pre-V1).

### §1.5 Click into expanded open-positions row (Tier-2 #3)
- [ ] Click an open-positions row.
- [ ] Row expands inline. If the ticker is in the latest pipeline's chart-scope set the chart `<img>` renders; if it isn't (the common case for held positions, since open-positions rotate out of chart-scope as the ticker drops out of A+ / near-trigger watchlist), a "Chart unavailable — …" message renders with the resolver's reason text.
- [ ] **Close button (✕)** at top-right of the expanded row collapses back to the compact row.
- [ ] Click the row a second time → re-expands cleanly (toggle works; no stale state).
- [ ] Exit + Adjust-stop buttons inside the compact row do NOT trigger the row expand on click (`event.stopPropagation()` guard per Bug-1 lesson).
- [ ] After clicking the dashboard's **Refresh now** button (POST /prices/refresh), the open-positions table re-renders via OOB swap and the click-to-expand binding still works on the refreshed rows (single-include guarantee — `prices_refresh_container.html.j2` uses the same partial). **Note (clarification 2026-04-28):** any visually-expanded row collapses back to compact form on refresh. This is expected HTMX OOB-swap behavior, NOT a regression — the OOB swap replaces the table HTML wholesale, so transient client-side expansion state resets. The click-to-expand BINDING survives (you can re-click to re-expand); the EXPANDED VISUAL STATE does not. Operator confirmed this is fine for V1; preserving expanded state across OOB swap would require either server-side session-tracked expansion state OR HTMX `hx-preserve` attributes — both deferred indefinitely.

### §1.4 Refresh-now button at bottom of dashboard
- [ ] Click "Refresh now" button.
- [ ] **Layout does NOT break** — heading "Watchlist - near trigger" stays visible; watchlist table doesn't butt up against open positions table (Bug 1 from Bugs.txt).
- [ ] Last-pipeline timestamp updates if a fresh run completed; OHLCV breaker also resets (Phase 3e.3).

---

## §2 Web surface — Standalone /watchlist

Navigate to `http://127.0.0.1:8080/watchlist`.

### §2.1 Watchlist render
- [ ] Page renders without 500 errors.
- [ ] Watchlist table renders ALL active watchlist entries (not just top-5).
- [ ] Pattern tag rendering matches dashboard top-5 (per §1.2): `flag (0.XX)` alongside existing tags for tickers with detected flag patterns.
- [ ] Sort order matches dashboard top-5 ordering (Phase 4 standalone /watchlist mixed-anchor fix).

### §2.2 Click into expanded row
- [ ] Same as §1.3.

---

## §3 Web surface — Chart image (overlay verification)

**Chart access paths (post Tier-2 #2 + #3):**

Three operator-accessible chart-view paths:

1. **Dashboard expanded watchlist row** — click a watchlist ticker to expand, chart appears inline (covered in §1.3).
2. **Dashboard expanded open-positions row** — click an open-positions row to expand, chart appears inline if the ticker is in chart-scope; otherwise the chart-unavailable reason renders (Tier-2 #3; covered in §1.5).
3. **Date-less chart URL `http://127.0.0.1:8080/charts/<TICKER>.png`** — Tier-2 #2 routes this to the latest completed pipeline's date-prefixed PNG (303 redirect to `/charts/<data_asof_date>/<TICKER>.png`), or returns a 404 page with the operator-facing chart-unavailable reason from `chart_scope.resolve_chart_scope`.

### §3.A Date-less chart URL verification (Tier-2 #2)

- [ ] Hit `http://127.0.0.1:8080/charts/<chart-scope-ticker>.png` (use a ticker known to be in latest pipeline's chart-scope set — see §0 step 3 for SQL to find them). The chart PNG renders in the browser; URL bar may settle on the date-prefixed URL after the silent 303 redirect.
- [ ] Hit `http://127.0.0.1:8080/charts/XYZNOTINSCOPE.png` (a clearly out-of-scope ticker). 404 page renders with the operator-facing reason message (e.g., "Chart unavailable — this ticker isn't in today's charting scope (A+ names + top near-trigger watchlist).").

### §3.B Remaining V1 known limitation

- **Chart-scope tickers NOT in watchlist** (e.g., A+ candidates without near-trigger ranking, or open-positions tickers that have rotated out of the watchlist sort): post-Tier-2-#2, the workaround is now hitting `/charts/<TICKER>.png` directly. Tier-2 #4 (chart-scope set alignment) still pending — when an operator's open position is OUT of the chart-scope set entirely (the common case after a few sessions), neither path renders a chart; the open-positions expand surface displays the chart-unavailable reason instead.

For a ticker with `pattern='flag'` (from §0 step 3), pick one that's still in the watchlist + chart-scope set; expand the row.

### §3.0 Chart-element legend (V1)

Charts paint several visual elements; the table below names them so failed checks can be reported precisely.

| Element | Style | Meaning |
|---|---|---|
| Candlesticks | green/red bars | Daily OHLC bars |
| 10MA | blue line | 10-day simple moving average |
| 20MA | orange line | 20-day SMA |
| 50MA | red line | 50-day SMA |
| Candidate-pivot hline | green dashed, full chart width | Operator's pivot price from candidate selection (pre-V1) |
| Stop hline | red dashed, full chart width | Operator's stop price |
| Pole band (overlay only) | light green fill, α=0.15 | Pole region detected by flag classifier (Phase 6) |
| Flag band (overlay only) | light yellow fill, α=0.15 | Flag region detected by flag classifier (Phase 6) |
| Algo-pivot segment (overlay only) | dark blue horizontal, spans flag region only | Algorithm's computed pivot — SEPARATE from the candidate-pivot hline |
| Consolidation marker | purple dotted vertical line | Right-edge boundary of the pattern-detection window (separates the window from the latest bar). Pre-existing pre-V1; not specific to flag overlay. |
| Volume panel | green/red bars below price panel | Daily volume |

If a chart shows an element this legend doesn't explain, surface to orchestrator as a doc gap (#14 family).

### §3.1 Chart title (mathtext fix verification)
- [ ] **Title reads cleanly** — for example: `AAPL | pivot 110.00 stop 95.00 | last 120 bars | flag (0.78)`.
- [ ] **The word "stop" is NOT italicized.** Pre-fix: matplotlib mathtext interpreted `$..$` as math mode and italicized "stop." Post-fix: `$` is omitted from the title format entirely, so math mode never engages.
- [ ] **No `$` glyphs in the title.** Trading context already implies dollar values; the labels "pivot" / "stop" carry the meaning.

### §3.2 Chart overlay (flag pattern detected — Phase 6)
- [ ] **Pole band** (light green, faint α=0.15) shaded over the pole region (typically 5-30 bars before the flag start).
- [ ] **Flag band** (light yellow, faint α=0.15) shaded over the flag region (5-21 bars adjacent to the pole, ending at the latest bar in the chart window).
- [ ] **Algo-pivot** — a dark blue horizontal segment at the pivot price level **spanning ONLY the flag region** (NOT full chart width). This is the algorithm's pivot.
- [ ] **Existing candidate-pivot hline** (green dashed, full chart width) is **PRESERVED** at the operator's pivot price. This is a SEPARATE visual element from the algo-pivot.
- [ ] **Stop hline** (red dashed, full chart width) at the stop price.
- [ ] If candidate-pivot and algo-pivot coincide visually (same price level), they overlap; otherwise they show as two distinct horizontal markings.

### §3.3 Chart for a non-flag ticker
- [ ] Navigate to a ticker WITHOUT a flag classification (e.g., a chart-scope ticker where `pattern='none'`).
- [ ] **No overlay bands or algo-pivot painted** — chart renders as it did pre-V1 (existing candidate-pivot hline + stop hline + SMAs + volume panel).
- [ ] Title format is the same except no `| flag (...)` suffix: `AAPL | pivot 110.00 stop 95.00 | last 120 bars`.

### §3.4 Chart for a classifier-error ticker (if any)
- [ ] If `§0 step 3` showed any classifier-error rows (`pattern IS NULL`), navigate to one of those tickers' charts.
- [ ] **No overlay painted** (matches non-flag behavior). `PatternOverlay.from_classification(r)` returns None for `pattern != 'flag'`, so the painting path is bypassed.

---

## §4 Web surface — Trade-entry form

Navigate to `http://127.0.0.1:8080/trades/entry/<TICKER>` for a ticker WITH a `pattern='flag'` classification.

### §4.1 Chart Pattern section (Phase 5)
- [ ] **"Chart pattern" section** appears between the sizing-hint block and the rationale field.
- [ ] **Algo display** shows `flag (0.78)` (or actual confidence) — exact format per the partial template.
- [ ] **Subtitle** shows `computed {timestamp}` (the cache row's `computed_at` value).
- [ ] **Override dropdown** with options: `Accept algo` (default; persists `chart_pattern_operator IS NULL`), `flag`, `none`, `other (specify)`.
- [ ] When `other (specify)` is selected, a free-text input field appears for operator's custom label.
- [ ] **Hidden snapshot inputs** for `chart_pattern_algo`, `chart_pattern_algo_confidence`, `chart_pattern_classification_pipeline_run_id` are present (visible via browser DevTools → Inspect → form HTML).

### §4.2 Submit form with default override (Accept algo)
- [ ] Fill in entry price, stop, etc. as usual.
- [ ] Leave override dropdown at `Accept algo`.
- [ ] Submit form.
- [ ] Trade record created successfully (redirect or success indicator).
- [ ] **Verify persistence** via SQLite:
  ```bash
  sqlite3 ~/swing-data/swing.db "
    SELECT id, ticker, chart_pattern_algo, chart_pattern_algo_confidence,
           chart_pattern_operator, chart_pattern_classification_pipeline_run_id
    FROM trades
    ORDER BY id DESC
    LIMIT 1"
  ```
- [ ] **Expected:** `chart_pattern_algo='flag'`, `chart_pattern_algo_confidence=<value>`, `chart_pattern_operator IS NULL` (operator accepted algo), `chart_pattern_classification_pipeline_run_id=<value>` (audit anchor).

### §4.3 Submit form with override = "flag" (operator agrees with algo)
- [ ] Different ticker. Fill in entry, stop. Override dropdown = `flag`.
- [ ] Submit.
- [ ] **Verify persistence:** `chart_pattern_operator='flag'` (operator explicitly agreed).

### §4.4 Submit form with override = "none" (operator disagrees with algo)
- [ ] Different ticker WITH `pattern='flag'` algo. Override dropdown = `none`.
- [ ] Submit.
- [ ] **Verify persistence:** `chart_pattern_algo='flag'` (algo unchanged), `chart_pattern_operator='none'` (operator overrode).

### §4.5 Submit form with override = "other" + free text
- [ ] Different ticker. Override dropdown = `other (specify)`. Free-text field: `pennant-like` (or similar custom label).
- [ ] Submit.
- [ ] **Verify persistence:** `chart_pattern_operator='pennant-like'` (canonicalized via `canonicalize_hypothesis_label` per spec §3.6 — NFC normalization + control-byte stripping).

### §4.6 Trade-entry form for ticker WITHOUT cached classification
- [ ] Navigate to `/trades/entry/<ticker_not_in_chart_scope>` (a ticker that didn't appear in the chart-scope set for the latest pipeline run).
- [ ] **"Not classified" stub** appears in the Chart Pattern section: e.g., "Not classified (out-of-scope or no recent pipeline run)".
- [ ] **No override dropdown surface** (override is hidden for un-cached tickers per spec §3.6 V1 cached-only constraint).
- [ ] **Form submits successfully WITHOUT chart_pattern fields populated** (all 4 chart_pattern columns persist as NULL).

### §4.7 Soft-warn confirm flow (Phase 5 Codex R1 M2 fix verification)
- [ ] Pick a ticker WITH cached `pattern='flag'` classification AND set up conditions to trigger a soft-warn (e.g., 4+ open trades to fire `SoftWarnError`).
- [ ] Submit the entry form.
- [ ] Soft-warn confirmation page appears.
- [ ] **Verify the chart_pattern hidden inputs ARE preserved** in the soft-warn confirm form (browser DevTools → Inspect → hidden inputs for `chart_pattern_algo`, etc.).
- [ ] Confirm/resubmit the trade.
- [ ] **Verify persistence (post-Phase-5 R1 M2 fix):** the snapshot is preserved end-to-end. Check the trade row has the chart_pattern fields populated AS-IS (not dropped to NULL).

---

## §5 CLI surface — `swing trade entry`

### §5.1 CLI with `--chart-pattern-operator` for ticker WITH cached classification
```bash
swing trade entry --ticker AAPL --entry-date 2026-04-27 --entry-price 110.00 --shares 10 --initial-stop 95.00 --rationale other --notes "manual verification test" --chart-pattern-operator flag
```
- Adjust `--ticker`, `--entry-date`, `--entry-price`, `--shares` to match a current cached-classification ticker.
- `--rationale` is `click.Choice([aplus-setup, near-trigger-breakout, vcp-breakout, pivot-breakout, post-earnings-continuation, relative-strength, other])` — see `swing trade entry --help`. For `other`, `--notes` is required (per spec parity with web form).
- All five `--ticker / --entry-date / --entry-price / --shares / --initial-stop` are required.

- [ ] **Command succeeds** (exit code 0).
- [ ] Trade record created.
- [ ] **Verify persistence:** `chart_pattern_operator='flag'` (operator override); `chart_pattern_algo='flag'` (from snapshot); `chart_pattern_algo_confidence=<value>`; `chart_pattern_classification_pipeline_run_id=<value>`.

### §5.2 CLI with `--chart-pattern-operator` for ticker WITHOUT cached classification
```bash
swing trade entry --ticker XYZX --entry-date 2026-04-27 --entry-price 50.00 --shares 1 --initial-stop 45.00 --rationale other --notes "manual test for refusal gate" --chart-pattern-operator flag
```
Use a ticker NOT in chart-scope for the latest pipeline run (e.g., one that doesn't appear in `pipeline_pattern_classifications.ticker` for the latest `pipeline_run_id`).

- [ ] **Command FAILS with non-zero exit code.**
- [ ] **Error message** (per spec §3.7-verbatim): something like `Error: --chart-pattern-operator requires a cached classification for XYZX; ticker is out-of-scope for the latest pipeline run. (V1 cached-only; manual fallback deferred to V2.)`.
- [ ] **No trade record created** (verify via `sqlite3 ~/swing-data/swing.db "SELECT * FROM trades WHERE ticker='XYZX' ORDER BY id DESC LIMIT 1"` — should return no row OR a previous row, not a fresh insert).

### §5.3 CLI WITHOUT `--chart-pattern-operator` (existing behavior, backward-compat)
```bash
swing trade entry --ticker AAPL --entry-date 2026-04-27 --entry-price 110.00 --shares 10 --initial-stop 95.00 --rationale other --notes "manual test"
```

- [ ] **Command succeeds** (existing CLI invocations without the flag still work).
- [ ] Trade record created with `chart_pattern_operator IS NULL` (no override) AND `chart_pattern_algo` etc. populated from cache snapshot if cached, OR all NULL if not cached.

---

## §6 Cross-surface consistency check

- [ ] Pick a ticker that's in chart-scope and has `pattern='flag'`.
- [ ] **Dashboard top-5 watchlist** renders the `flag (0.XX)` tag.
- [ ] **Standalone /watchlist** renders the SAME tag with the SAME confidence value.
- [ ] **Trade-entry form** displays the SAME confidence value in the Chart Pattern section.
- [ ] **Chart image** title shows the SAME confidence value in the `| flag (0.XX)` suffix.
- [ ] All four surfaces agree on the displayed confidence value (they read from the same `pipeline_pattern_classifications` row via `pipeline_run_id` audit anchor).

---

## §7 What to do if something fails

1. **Take a screenshot** (or note the URL + DevTools data).
2. **Capture the SQLite state** for the affected ticker + pipeline run:
   ```bash
   sqlite3 ~/swing-data/swing.db "
     SELECT * FROM pipeline_pattern_classifications
     WHERE ticker = '<TICKER>' AND pipeline_run_id = <PIPELINE_RUN_ID>"
   ```
3. **Note which check failed** — referencing this doc's section number (§N.M).
4. **Surface to orchestrator** with: (a) section + check that failed; (b) actual vs expected behavior; (c) screenshot or HTML snippet; (d) SQLite state if relevant.

The orchestrator will triage and decide whether the failure is:
- A bug requiring a small follow-up commit.
- An expected V1 limitation (e.g., classifier-error rendering; the spec deliberately treats these as "not classified").
- A spec ambiguity that needs amendment.
- A fixture/data issue (e.g., the latest pipeline didn't classify any flags).

---

## §8 Walkthrough completion

When all sections complete with checks passing:

- [ ] Note the timestamp and pipeline_run_id used for verification.
- [ ] If any check failed (even one), surface to orchestrator before proceeding to Task 7.3 fixture labeling.
- [ ] If all checks pass, the V1 chart-pattern surface is operator-verified across both web + CLI. Proceed to Task 7.3 fixture labeling at your own pace.
- [ ] Optionally amend this doc if any check should be added/removed/refined for future verification cycles.

**Estimated time:** 30-45 min thorough walkthrough; ~10-15 min if just spot-checking key surfaces (§1.2 + §3.2 + §4.1 + §5.1 + §5.2).

---

## Post-V2 chart-scope policy (2026-04-27)

After migration `0011` (chart-scope policy v2), `pipeline_chart_targets.source` accepts FOUR values: `aplus`, `near_proximity` (legacy, read-only post-migration), `open_position`, `tag_aware_top_n`.

Chart-scope set per pipeline run is now the precedence-ordered union:

1. `aplus` — A+ candidates (unchanged from V1).
2. `open_position` — currently-open trades from `list_open_trades(conn)`. Pivot from `trades.entry_price`, stop from `trades.current_stop`. **Charts are generated during the scheduled pipeline run; a position opened AFTER the latest completed run remains unchartable until the next pipeline run.**
3. `tag_aware_top_n` — top-N watchlist (default N=10, was 5) by Phase 4 4-key composite (tag count DESC, tag precedence DESC, proximity ASC, ticker ASC).

Deduplication precedence: `aplus > open_position > tag_aware_top_n`. A ticker in multiple tiers is recorded ONCE under the highest-precedence source.

### Verification queries (post-migration)

```sql
-- All chart-scope tickers for the latest completed run, with source
SELECT ticker, source, chart_status
FROM pipeline_chart_targets
WHERE pipeline_run_id = (
    SELECT id FROM pipeline_runs
    WHERE state = 'complete' ORDER BY finished_ts DESC, id DESC LIMIT 1
)
ORDER BY ticker;

-- Distribution of source values across the latest run
SELECT source, COUNT(*) AS cnt
FROM pipeline_chart_targets
WHERE pipeline_run_id = (
    SELECT id FROM pipeline_runs
    WHERE state = 'complete' ORDER BY finished_ts DESC, id DESC LIMIT 1
)
GROUP BY source;
```

### Wall-time monitoring

Each pipeline run logs `chart-step wall-time` if the chart step exceeds soft (60s) or hard (120s) budgets. Search pipeline-run logs for `chart-step wall-time exceeded`. If repeated overrun: dispatch a follow-up to reduce `chart_top_n_watch` from 10 to 5 OR implement tier-based shedding (see spec §A "Future hardening").

### Stop hline omission

Trades with `current_stop = NULL` or `current_stop = 0.0` render WITHOUT a stop hline (post-2026-04-27). Confirm visually if you encounter such a trade — the chart still renders pivot but no stop horizontal line, and the title omits the `stop X.XX` segment.
