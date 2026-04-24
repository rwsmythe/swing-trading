# Swing Trading — Cycle Checklist

Working routine for the refactored stack (Phase 3d+). Assumes `swing` is on PATH
(Scripts dir added permanently to Windows user PATH).

---

## Daily — Pre-market (evening or morning before open)

### 1. Drop the Finviz CSV

- Export from Finviz with the **13 required columns**:
  `No., Ticker, Sector, Industry, Country, Price, Change, Average Volume,
  Relative Volume, Average True Range, 52-Week High, 52-Week Low, Market Cap`
- Save to `data/finviz-inbox/finvizDDMmmYYYY.csv` (e.g. `finviz19Apr2026.csv`)
- Tip: save a custom Finviz layout with this schema so export is mechanical

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

---

## Flag tag glossary (briefing + dashboard)

- **TT✓** — passes Minervini Trend Template (7 of 8 criteria, with TT8 RS-rank the allowed miss)
- **VCP✓** — all VCP (Volatility Contraction Pattern) criteria pass
- **A+** — `aplus` bucket — strongest setup, actionable today
- **watch** — on watchlist but not actionable yet
- **near_trigger** — within the asymmetric window of a pivot breakout (see `[near_trigger]` in `swing.config.toml`)
