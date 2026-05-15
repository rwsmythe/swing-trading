# Swing Trading — Cycle Checklist

Working routine for the refactored stack (Phase 3d+). Assumes `swing` is on PATH
(Scripts dir added permanently to Windows user PATH).

---

## Initial setup — Schwab API integration (one-time)

After project install + before first pipeline run that consumes Schwab data:

1. **Register Schwab Developer Portal app.**
   - Visit [developer.schwab.com](https://developer.schwab.com/).
   - Create new app; name e.g. "Swing Trading Personal".
   - Request Trader API + Market Data API access.
   - Configure callback URL to `https://127.0.0.1` (paste-back flow; no listener required).
   - Note `client_id` + `client_secret`.
   - Await production-tier approval (Schwab review; days to weeks).

2. **Run setup:**

   ```powershell
   swing schwab setup --environment production
   # -> prompts for client_id + client_secret (secret is hidden input)
   # -> prints consent URL
   # -> open URL in browser, log in, approve
   # -> browser redirects to https://127.0.0.1/?code=<CODE>... (404 page; copy the FULL redirected URL from the address bar)
   # -> paste redirected URL at CLI prompt
   # -> CLI persists tokens DB at ~/swing-data/schwab-tokens.production.db (or .json depending on schwabdev version)
   # -> CLI auto-picks (single account) or prompts for primary account_hash if multiple
   # -> CLI writes integrations.schwab.account_hash to user-config.toml
   ```

3. **Activate environment** (V1 — `swing config set` does NOT cover
   `integrations.schwab.environment`; hand-edit `~/swing-data/user-config.toml`
   to set it, OR pass `--environment production` on each Schwab CLI invocation):

   ```powershell
   # Option A — hand-edit ~/swing-data/user-config.toml:
   #   [integrations.schwab]
   #   environment = "production"
   notepad "$env:USERPROFILE\swing-data\user-config.toml"

   swing schwab status   # confirm tokens DB valid; account_hash set; env reads "production"
   ```

4. **Verify first fetch:**

   ```powershell
   swing schwab fetch --snapshot   # writes one account_equity_snapshots row
   swing schwab fetch --orders     # writes one reconciliation_run + any discrepancies
   ```

5. **(Optional) Sandbox mode for cassette recording:**

   ```powershell
   swing schwab setup --environment sandbox   # separate sandbox app credentials
   # Sandbox is verification-only: API calls + audit rows; ZERO domain writes.
   ```

---

## Daily — Pre-market (evening or morning before open)

### 1. Finviz screen — automated via API

- ~~Export Finviz screen as CSV named `finvizDDMmmYYYY.csv` and drop in
  `data/finviz-inbox/`.~~
  **Replaced 2026-05-06:** the pipeline now fetches the screen automatically via
  the Finviz Elite API (see `_step_finviz_fetch` in `swing/pipeline/runner.py`).
  Manual export remains supported as a fallback if the API fails or the operator
  wants to override the day's screen — drop the file in the inbox before
  triggering the pipeline and the API fetch will skip
  (logs `skipped_manual_override`).
- (NEW) Inspect `swing finviz status` weekly to confirm rate-limit headroom +
  watch for the `signature changed since prior run` WARNING (indicates operator
  edited the saved screen).
- Manual fallback format (when needed): the **13 required columns** are
  `No., Ticker, Sector, Industry, Country, Price, Change, Average Volume,
  Relative Volume, Average True Range, 52-Week High, 52-Week Low, Market Cap`;
  filename `finvizDDMmmYYYY.csv` with 1-2 digit day, e.g. `finviz5May2026.csv`.

### 2. Run the nightly pipeline

```powershell
swing pipeline run
```

Expected: 2–5 minutes. Look for `Run id N: state=complete`.

If it hangs: Ctrl-C, `swing pipeline list`, then
`swing pipeline force-clear <id> --bypass-staleness-check` if genuinely stuck.

### 3. Review the briefing

```powershell
start exports/YYYY-MM-DD/briefing.html
```

Or markdown: `Get-Content exports/YYYY-MM-DD/briefing.md -Encoding UTF8`

Check:
- Weather status (Bullish / Caution / Bearish) + rationale
- Today's Decisions (A+ setups actionable)
- Watchlist (near-pivot tickers with stop suggestions)
- Position count vs caps (e.g. `0 / 4 warn, cap 6`)
- **Verify briefing.md Schwab section.** Each pipeline run's `briefing.md` now
  includes a "Schwab integration" section reporting latest equity snapshot +
  reconciliation discrepancy count. If banner "Schwab integration: degraded"
  appears, run `swing schwab status` to diagnose.

---

## Daily — During market hours

### 4. Open the dashboard

```powershell
swing web
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

Smoke-check on first load:
- Weather shows correct status (not "Stale")
- Account equity matches expectation
- Open positions render; advisories visible on any trade with fireable rules
- No persistent red/yellow banners

### 5. Act on A+ decisions (rare)

If briefing flagged an A+ setup you want to take:

```powershell
swing trade entry `
  --ticker <TICKER> `
  --entry-price <PRICE> `
  --shares <N> `
  --initial-stop <STOP> `
  --entry-date <YYYY-MM-DD> `
  --rationale "near-pivot from <DATE> watchlist (pivot $X, -Y%)"
```

**Discipline gate:** `--rationale` is required. If you can't articulate why, don't take the trade.

### 6. Act on open-position advisories

Refresh the dashboard. For any trade with advisories showing:

- **`trail_10ma` / `trail_20ma`** → raise stop:
  ```powershell
  swing trade stop-adjust --trade-id <ID> --new-stop <NEW> --rationale "trail_10ma: to 0.3% below 10MA"
  ```
- **`exit_below_10ma/20ma/50ma`** → yesterday's close broke support; exit:
  ```powershell
  swing trade exit --trade-id <ID> --shares <REMAINING> --exit-price <PX> --exit-date <DATE> --reason manual --rationale "exit_below_<N>ma fired"
  ```
- **`breakeven`** → move stop to entry price
- **`time_stop`** → trade has gone nowhere in 10 days; consider exit
- **`weather_action`** → market regime changed; consider de-risking

---

## Daily — Post-close

### 7. Final review

```powershell
swing trade list                    # open positions
swing journal review --period month # MTD stats + behavioral flags
```

Behavioral flags to watch for:
- **Low win rate** (< 35%)
- **Large avg loss** (> 1R)
- **Overtrading** (position count at cap repeatedly)

### 8. Journal any cash movements

Deposits / withdrawals from the broker account (keeps journal = broker reality):

```powershell
swing journal cash --deposit 500 --date 2026-04-20 --note "monthly contribution"
swing journal cash --withdraw 200 --date 2026-04-20 --note "withdrawal"
```

---

## Weekly (Friday post-close or weekend)

- **Verify Schwab refresh_token validity.** Run `swing schwab status` weekly.
  Schwab production-tier refresh_tokens have ~90-day TTL; sandbox-tier ~7 days.
  If `refresh_token: valid (N days remaining)` shows < 14 days, plan to run
  `swing schwab setup` again to re-bootstrap before expiry.

### 9. Reconcile against TOS

Download the ToS Account Statement covering the week. Save as:

```
thinkorswim/YYYY-MM-DD-AccountStatement.csv
```

Then dry-run first:

```powershell
swing tos-import --csv "thinkorswim/YYYY-MM-DD-AccountStatement.csv" --dry-run
```

If the report looks right (cash moves you expect, fills match your trades), commit:

```powershell
swing tos-import --csv "thinkorswim/YYYY-MM-DD-AccountStatement.csv" --auto-confirm
```

If mismatches appear (broker says X, journal says Y), **investigate before committing** — never let mismatches auto-resolve.

### 10. Backup the DB

```powershell
$stamp = Get-Date -Format "yyyyMMdd"
Copy-Item "$env:USERPROFILE\swing-data\swing.db" "$env:USERPROFILE\swing-data\backups\swing.db.$stamp.bak"
```

Keeps a known-good rollback point. The `~/swing-data/backups/` dir accumulates; prune manually if size becomes a concern.

---

## Monthly

### 11. Journal review — monthly cadence

```powershell
swing journal review --period month
swing journal review --period ytd
```

Examine:
- Expectancy (positive R per trade)
- Win rate trending
- Behavioral flags accumulating
- Streak state

If the system is profitable: stay disciplined.
If not: figure out why *before* the next trade.

### 12. Refresh RS universe (if needed)

The RS universe versions itself; the pipeline will warn on stale data. Typically no action required monthly, but:

```powershell
swing rs-universe --help
```

### 13. Archive old CSVs

`data/finviz-inbox/rejected/` accumulates from validation failures. Prune if large.
`thinkorswim/` accumulates. Keep at least 3 months for audit.

---

## Invariants (don't break these)

- **DB stays at `%USERPROFILE%/swing-data/swing.db`** — NOT inside the Drive folder
- **Branch: `main`** — no feature branches for this project
- **Conventional commits** for any code changes: `feat(x): ...`, `fix(x): ...`, etc.
- **No trade without `--rationale`** — the CLI enforces this; don't work around it
- **Reconcile weekly** — drift between journal and broker compounds silently

---

## Troubleshooting quick-ref

| Symptom | Likely cause | Fix |
|---|---|---|
| Dashboard or other template crashes with `UndefinedError: 'X object has no attribute Y'` | Web server process predates latest code; Python dataclass definitions stale while Jinja templates reloaded | Restart `swing web` (Ctrl-C the running process, re-run `swing web`) |
| "command not found: swing" | PATH not set | Add `%APPDATA%\Python\Python314\Scripts` to user PATH (permanent) |
| Pipeline run hangs at `evaluate` | yfinance slow or 69+ tickers | Wait 5 min; Ctrl-C + force-clear if truly stuck |
| "SMA advisories unavailable" banner | yfinance rate-limit tripped OhlcvCache | Wait 60s, hard-refresh |
| Weather shows "Stale" | Pipeline hasn't run for today's action session | Run `swing pipeline run` |
| Watchlist prices (stale) | Market closed; showing last-close fallback | Expected on weekends / after hours |
| Dashboard doesn't auto-refresh after pipeline | Fixed post-walkthrough; auto-reloads 1.5s after terminal state | Hard-refresh (Ctrl+F5) as fallback |
| Finviz CSV rejected | Missing required columns | Check `data/finviz-inbox/rejected/*.rejected-reasons.json` |

### Schwab integration recovery

- **Schwab refresh_token expired or revoked at Schwab Developer Portal:**

  ```powershell
  swing schwab logout
  swing schwab setup --environment production
  swing schwab fetch --snapshot   # verify recovery
  ```

- **Schwab Developer Portal app reapproval / scope change:**

  ```powershell
  swing schwab logout
  swing schwab setup --environment production
  ```

- **Tokens DB corruption:**

  ```powershell
  Remove-Item "$env:USERPROFILE\swing-data\schwab-tokens.production.db"
  swing schwab setup --environment production
  ```

---

## Flag tag glossary (briefing + dashboard)

- **TT✓** — passes Minervini Trend Template (7 of 8 criteria, with TT8 RS-rank the allowed miss)
- **VCP✓** — all VCP (Volatility Contraction Pattern) criteria pass
- **A+** — `aplus` bucket — strongest setup, actionable today
- **watch** — on watchlist but not actionable yet
- **near_trigger** — within the asymmetric window of a pivot breakout (see `[near_trigger]` in `swing.config.toml`)
