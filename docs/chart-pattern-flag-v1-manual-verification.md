# Chart-Pattern Flag-V1 — Manual Verification Procedure

**Purpose:** Step-by-step procedure for the operator to manually verify chart-pattern flag-v1 displays correctly across web + CLI surfaces after Phase 6 (build phases complete) + Phase 7 implementer-side (test infrastructure) ship.

**When to run:** After Phase 7 implementer-side dispatch ships Tasks 7.1 + 7.2; ideally BEFORE operator begins Task 7.3 fixture labeling work (so any UI bugs surface before they affect labeling efficiency).

**Expected duration:** ~30-45 minutes for a thorough walkthrough.

**Prerequisites:**
- swing-trading repo at HEAD with Phase 7 implementer-side shipped (or at minimum Phase 6 complete + mathtext fix `2fd0ecc` landed).
- Production DB at `~/swing-data/swing.db` with schema_version = 10.
- A recent pipeline run with classifications populated in `pipeline_pattern_classifications` table.
- `swing` CLI on PATH (`%APPDATA%\Python\Python314\Scripts\` per CLAUDE.md).

---

## §0 Pre-flight checks

Before walking through the surfaces, confirm baseline state:

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
    SUM(CASE WHEN ppc.pattern IS NULL THEN 1 ELSE 0 END) AS classifier_error_count
  FROM pipeline_runs pr
  LEFT JOIN pipeline_pattern_classifications ppc ON ppc.pipeline_run_id = pr.id
  WHERE pr.state = 'complete'
  GROUP BY pr.id
  ORDER BY pr.finished_ts DESC
  LIMIT 5"
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
- [ ] **Account card** displays starting equity + realized P&L + net cash + **Unrealized P&L** line item (Phase 3e.1; shipped pre-V1).
- [ ] **Open positions** table renders without 500 errors. If you have open trades, they appear.

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

For a ticker with `pattern='flag'` (from §0 step 3), navigate to its chart via the dashboard expanded row OR directly via `http://127.0.0.1:8080/charts/<TICKER>.png`.

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
- [ ] Pick a ticker WITH cached `pattern='flag'` classification AND set up conditions to trigger a soft-warn (e.g., 4+ open trades to fire `SoftWarnException`).
- [ ] Submit the entry form.
- [ ] Soft-warn confirmation page appears.
- [ ] **Verify the chart_pattern hidden inputs ARE preserved** in the soft-warn confirm form (browser DevTools → Inspect → hidden inputs for `chart_pattern_algo`, etc.).
- [ ] Confirm/resubmit the trade.
- [ ] **Verify persistence (post-Phase-5 R1 M2 fix):** the snapshot is preserved end-to-end. Check the trade row has the chart_pattern fields populated AS-IS (not dropped to NULL).

---

## §5 CLI surface — `swing trade entry`

### §5.1 CLI with `--chart-pattern-operator` for ticker WITH cached classification
```bash
swing trade entry --ticker AAPL --entry 110.00 --stop 95.00 --chart-pattern-operator flag --rationale "manual test"
# (Adjust ticker + prices to match a current cached-classification ticker)
```

- [ ] **Command succeeds** (exit code 0).
- [ ] Trade record created.
- [ ] **Verify persistence:** `chart_pattern_operator='flag'` (operator override); `chart_pattern_algo='flag'` (from snapshot); `chart_pattern_algo_confidence=<value>`; `chart_pattern_classification_pipeline_run_id=<value>`.

### §5.2 CLI with `--chart-pattern-operator` for ticker WITHOUT cached classification
```bash
swing trade entry --ticker XYZX --entry 50.00 --stop 45.00 --chart-pattern-operator flag --rationale "manual test"
# (Use a ticker NOT in chart-scope for the latest pipeline run)
```

- [ ] **Command FAILS with non-zero exit code.**
- [ ] **Error message** (per spec §3.7-verbatim): something like `Error: --chart-pattern-operator requires a cached classification for XYZX; ticker is out-of-scope for the latest pipeline run. (V1 cached-only; manual fallback deferred to V2.)`.
- [ ] **No trade record created** (verify via `sqlite3 ~/swing-data/swing.db "SELECT * FROM trades WHERE ticker='XYZX' ORDER BY id DESC LIMIT 1"` — should return no row OR a previous row, not a fresh insert).

### §5.3 CLI WITHOUT `--chart-pattern-operator` (existing behavior, backward-compat)
```bash
swing trade entry --ticker AAPL --entry 110.00 --stop 95.00 --rationale "manual test"
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
