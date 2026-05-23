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

2. **Persist `client_id` + `client_secret` once (cfg-cascade tier 2; Phase 12 Sub-bundle B):**

   ```powershell
   swing config set integrations.schwab.client_id <CLIENT_ID>
   swing config set integrations.schwab.client_secret <CLIENT_SECRET>
   # -> writes both to ~/swing-data/user-config.toml under [integrations.schwab]
   # -> swing.config.toml MUST NOT contain these (sensitive)
   ```

   Cascade for credential resolution (Phase 12 Sub-bundle A + B): **env vars
   (`SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET`) > cfg fields
   (`integrations.schwab.{client_id,client_secret}`) > interactive prompt**.
   Partial env-tier (only one of the two set) STILL raises by design
   (Sub-bundle A T-A.1 LOCK); partial cfg-tier falls through to prompt
   (Sub-bundle B T-B.1 LOCK — file-tier is operator-friendly).

3. **Run setup — web (PRIMARY, Phase 12 Sub-bundle B):**

   ```powershell
   swing web
   # -> open http://127.0.0.1:8080/schwab/setup
   # -> form auto-fills client_id/client_secret from cfg cascade (no prompt if step 2 done)
   # -> click "Authorize at Schwab" link (opens Schwab consent page in new tab)
   # -> approve; Schwab redirects to https://127.0.0.1/?code=<CODE>... (404 page; copy FULL URL from address bar)
   # -> paste URL into the form; submit
   # -> server-side manual token exchange against /v1/oauth/token; tokens written atomically
   # -> HX-Redirect to /config?schwab_setup=ok on success
   ```

   Sub-bundle A T-A.2 self-healing applies identically: a stale tokens DB
   from a prior expired refresh_token is auto-detected + renamed to
   `*.deleted-<ts>` before the new tokens are written. The web flow no
   longer requires the prior `logout → setup` recovery sequence.

4. **Run setup — CLI (FALLBACK; multi-account OR web unavailable):**

   ```powershell
   swing schwab setup --environment production
   # -> credentials resolved via cascade (env > cfg > prompt); secret is hidden input on prompt
   # -> prints consent URL
   # -> open URL in browser, log in, approve
   # -> browser redirects to https://127.0.0.1/?code=<CODE>... (404 page; copy the FULL redirected URL from the address bar)
   # -> paste redirected URL at CLI prompt
   # -> CLI persists tokens DB at ~/swing-data/schwab-tokens.production.db (or .json depending on schwabdev version)
   # -> CLI auto-picks (single account) or prompts for primary account_hash if multiple
   # -> CLI writes integrations.schwab.account_hash to user-config.toml
   ```

   Use CLI when: multi-account selection needed (web V1 auto-picks the
   singleton and raises on multi-account per Sub-bundle B T-B.4 LOCK), OR
   when the web server is unavailable.

5. **Activate environment** (V1 — `swing config set` does NOT cover
   `integrations.schwab.environment`; hand-edit `~/swing-data/user-config.toml`
   to set it, OR pass `--environment production` on each Schwab CLI invocation):

   ```powershell
   # Option A — hand-edit ~/swing-data/user-config.toml:
   #   [integrations.schwab]
   #   environment = "production"
   notepad "$env:USERPROFILE\swing-data\user-config.toml"

   swing schwab status   # confirm tokens DB valid; account_hash set; env reads "production"
   ```

6. **Verify first fetch:**

   ```powershell
   swing schwab fetch --snapshot   # writes one account_equity_snapshots row
   swing schwab fetch --orders     # writes one reconciliation_run + any discrepancies
   ```

7. **(Optional) Sandbox mode for cassette recording:**

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
- **Verify briefing.md Schwab degraded banner.** Each pipeline run's
  `briefing.md` will include a "Schwab integration: degraded" banner if the
  most recent Schwab API call failed. Run `swing schwab status` to diagnose.
  (Full Schwab snapshot + reconciliation-summary section is V2 work — V1
  surfaces those metrics via `swing schwab status` instead.)

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
  Schwab refresh_tokens have ~7-day TTL (both sandbox and production tiers per
  operator-paired-gate observation 2026-05-14). If `refresh_token: valid (N days
  remaining)` shows < 2 days remaining, re-bootstrap before expiry:
  - **Primary path (Phase 12 Sub-bundle B):** open
    [http://127.0.0.1:8080/schwab/setup](http://127.0.0.1:8080/schwab/setup)
    in the running web server (`swing web`). The form pre-fills credentials
    from the cfg cascade + handles paste-back entirely in the browser; no
    PowerShell drop-out required. T-A.2 self-healing renames any stale
    tokens DB atomically before writing.
  - **Fallback path (CLI):** `swing schwab logout` →
    `swing schwab setup --environment production`. Use when web is
    unavailable or operator prefers terminal flow.

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

### 9.bis Schwab reconciliation — Tier-2 ambiguity review (Phase 12 Sub-bundle C)

After any Schwab reconciliation pipeline run (`swing pipeline run` with the
Schwab integration active), tier-1 unambiguous discrepancies auto-correct
journal-from-Schwab in-flow. Tier-2 ambiguous discrepancies (e.g., qty
mismatches that could be a partial fill OR a missed split) land in
`resolution='pending_ambiguity_resolution'` for operator decision.

1. **Surface the tier-2 backlog:**

   ```powershell
   swing journal discrepancy list-pending-ambiguities
   # -> filters available: --ambiguity-kind <kind>, --ticker <TICKER>, --limit <N>
   ```

2. **Inspect the per-discrepancy menu** to read the candidate choices, their
   `requires_custom_value` flags, and expected JSON shapes:

   ```powershell
   swing journal discrepancy show-ambiguity <discrepancy_id>
   ```

3. **Decide based on operator context + broker-statement consultation.** Pick
   a `--choice` code from the menu + supply a free-text `--reason`. Some
   choices require `--custom-value '<json>'` per the spec §6.2.1 contract
   (the `show-ambiguity` output flags these explicitly):

   ```powershell
   swing journal discrepancy resolve-ambiguity <discrepancy_id> `
     --choice <code> `
     --reason "consulted Schwab Account Activity; partial fill at 13:42" `
     [--custom-value '{"qty": 50}']
   ```

   `--reason` is REQUIRED (spec §6.4 mandatory; persisted on the new
   `reconciliation_corrections` row as `correction_reason`). The
   `--schwab-api-call-id <N>` flag is optional — supply it when the backfill
   Pass-2 dry-run output (see §9.ter) emitted a `call_id=<N>` line for the
   discrepancy to chain the audit row.

4. **Web alternative:** click the dashboard banner link to open the resolve
   form for the oldest pending-ambiguity row; pick a choice from the menu;
   type a reason; submit. The CLI `swing journal discrepancy resolve-ambiguity`
   remains available for power-user / scripted flows. Web-resolved rows are
   distinguishable from CLI-resolved rows via
   `reconciliation_discrepancies.resolved_by` (`operator_web` vs `operator`).

### 9.ter One-time backfill (first run after Phase 12 Sub-bundle C ships)

The backfill CLI replays the auto-correct + tier-2 classifier across every
pre-existing `resolution='unresolved'` discrepancy from before Sub-bundle C
landed. Run it ONCE after the migration; future emits are auto-corrected
in-flow via the reconciliation pivot.

1. **Dry-run first** to preview the classification matrix without writing:

   ```powershell
   swing journal reconcile-backfill --dry-run
   ```

   Inspect the projection: tier counts (tier1 / tier2 / unsupported), per-row
   `call_id=<N>` hints for tier-2 resolution chaining, and any Pass-2 Schwab
   API call estimates. Add `--ticker CVGI` (or any single ticker) to scope
   the dry-run to a single ticker for confidence.

2. **Apply when ready:**

   ```powershell
   swing journal reconcile-backfill --apply
   # or scope: swing journal reconcile-backfill --apply --ticker CVGI
   ```

   Optional flags: `--no-pass-2-on-dry-run` (skip Pass-2 Schwab calls during
   dry-run); `--retry-pass-2-failures` (re-attempt Pass-2 on prior
   backfill-attempt failures); `--limit <N>` (cap the iteration).

### 9.quater Tier-3 operator override (rare)

When the operator has ground-truth evidence that Schwab is wrong (e.g.,
broker-statement contradicting Schwab's API response, or a prior tier-1
auto-correction that the operator wants to revert + replace with the true
value), use `override-correction`:

1. **Identify the prior `correction_id`** via the discrepancy's audit chain:

   ```powershell
   swing journal discrepancy show <discrepancy_id>
   # -> lists the linked reconciliation_corrections row(s)
   ```

2. **Apply the override:**

   ```powershell
   swing journal discrepancy override-correction <correction_id> `
     --truth-value '{"price": 5.25}' `
     --reason "operator-verified from Schwab Account Activity 2026-05-14"
   ```

   Confirmation prompt fires by default. For non-interactive automation
   (scripted runs), add `--force`. `--truth-value` JSON is validator-chain
   re-validated BEFORE any mutation (spec §5.7 Codex R1 Minor #1 reorder);
   `AlreadySupersededError` surfaces as a friendly CLI error naming the
   current chain-head correction_id when the row has already been
   superseded.

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

## Quarterly diagnostics (Phase 13 T4.SB)

- Re-run `swing diagnose aplus-sensitivity --eval-runs 63 --output-dir exports/diagnostics/`
  to detect criterion calibration drift. Archive prior outputs to
  `exports/diagnostics/archive/` before re-running.
- Re-run `swing diagnose metrics-wiring --output exports/diagnostics/metrics-wiring-audit-<ISO>.md`
  to detect wiring drift on metric surfaces.
- Operator reviews output + banks V2 candidates if drift surfaces.

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

  Primary path (web; Phase 12 Sub-bundle B): open
  [http://127.0.0.1:8080/schwab/setup](http://127.0.0.1:8080/schwab/setup);
  paste callback URL; submit. T-A.2 self-healing handles the stale-tokens-DB
  rename automatically. Then verify:

  ```powershell
  swing schwab fetch --snapshot   # verify recovery
  ```

  Fallback path (CLI):

  ```powershell
  swing schwab logout
  swing schwab setup --environment production
  swing schwab fetch --snapshot
  ```

- **Schwab Developer Portal app reapproval / scope change:**

  Web (primary): open `/schwab/setup` + repeat the paste-back flow.

  CLI (fallback):

  ```powershell
  swing schwab logout
  swing schwab setup --environment production
  ```

- **Tokens DB corruption:**

  ```powershell
  swing schwab logout                   # preserves 24h recovery window
  swing schwab setup --environment production
  ```

  If `swing schwab logout` fails because the tokens DB is corrupt enough to
  block all CLI commands, fall back to manual removal as a last resort:

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

---

## Cross-reference: orchestrator-side housekeeping (NOT operator-cadence)

The checklist above covers your daily / weekly / monthly trading routine. Claude Code orchestrator/dev workflow disciplines — post-merge housekeeping commits, CLAUDE.md status-line size-check trigger, archive-split cadence, retention rules for `docs/phase3e-todo.md` + `docs/orchestrator-context.md` + `docs/CLAUDE.md-archive.md` — live at [`docs/orchestrator-context.md`](docs/orchestrator-context.md) §"Maintenance: retention discipline". Those fire during Claude Code dev sessions; they do not appear in your trading routine and you do not need to track them yourself. The orchestrator self-checks at housekeeping-commit time (per the size-check trigger added 2026-05-18 PM).
