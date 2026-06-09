# Phase 16 — Observability & Logging (TODO)

**Opened:** 2026-06-08 (operator-commissioned at the close of the Phase-15 mandate). **Theme:** observability + a logging-system overhaul. **Status:** DRAFT — this is an initial todo list to iterate on, not a commitment. Each arc below gets its own copowers cycle (brainstorm → writing-plans → executing) or a focused executing-with-Codex when picked up. Schema impact is per-arc (most are runtime/logging, NO schema; the optional yfinance-audit table would be a migration).

**Why this phase (the triggering diagnosis):** a web-triggered pipeline run (#96, 2026-06-08) took **~10m25s**. The DB showed it completed cleanly, but **Schwab calls accounted for only 25.5s — all crammed into the final ~55s — leaving ~570s (9.5 min) of pre-Schwab work with ZERO timing visibility.** That early work is yfinance-bound (`PriceCache`/`OhlcvCache`/`read_or_fetch_archive`) in the evaluate/detect/observe steps, whose load grew with the #23 pool-widening (34 exemplars, 15 failing yfinance fetches; ~200+ forward detections each needing a bar). We could only *infer* the cause because the logging doesn't capture it — which is the impetus for this phase.

---

## The current logging landscape (grounded 2026-06-08)

| Surface | State |
|---|---|
| **web.log** | `configure_web_logging(logs_dir)` ([app.py:441](../swing/web/app.py); rotating handler in [middleware/request_id.py](../swing/web/middleware/request_id.py)). The ONLY configured file log. |
| **pipeline.log** | **DOES NOT EXIST.** The web spawns the pipeline subprocess with `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL` ([web/routes/pipeline.py:129](../swing/web/routes/pipeline.py)) and nothing configures a `pipeline.log` handler — yet the error messages tell operators to "check `swing-data/logs/pipeline.log`" (a file that's never created). The runner's per-step `log.info` + its built-in slow-step warning (`_walltime_elapsed > 60s/120s` at [runner.py:3214](../swing/pipeline/runner.py)) are **discarded** for web-triggered runs. |
| **CLI** | No dedicated log file; ad-hoc. |
| **Central config** | **None.** No `[logging]` config section, no log-LEVEL knob. `finviz_api.py` does ad-hoc per-logger level juggling (`_TRANSPORT_DEBUG_LOGGERS`). |
| **Secret redaction** | The Schwab `logging.setLogRecordFactory` redaction (`ensure_schwab_log_redaction_factory_installed`, process-global, [client.py:197/201](../swing/integrations/schwab/client.py)) — installed defensively before Schwab calls in ~12 sites. The only redaction layer. |
| **Audit/timing tables** | `schwab_api_calls` (per-Schwab-call `response_time_ms` + `pipeline_run_id`). **yfinance calls are unaudited.** `pipeline_runs` records per-step STATUS but **no per-step DURATION**. |
| **Retention** | **225MB** in `~/swing-data/logs/`; rotated `web.log.2026-05-23` = **97MB**, `web.log.2026-05-06` = **83MB** — rotation exists but **old files are never cleaned up**, and the current web.log is 53MB (high volume — likely an unaudited verbosity/noise issue). |

---

## Arc 1 — Pipeline-run observability (the triggering arc; highest priority)

**Goal:** turn the *next* slow run into a precise per-step attribution (which step owns the time), so we can then make an informed perf decision. Small, high-leverage.

- [ ] **1a — Stop discarding the pipeline subprocess output.** Either redirect the web-spawned Popen `stdout/stderr` to `swing-data/logs/pipeline.log` (the path the errors already reference), OR have `swing pipeline run` configure its OWN rotating `pipeline.log` file handler (preferred — a file handler is independent of the parent's stdout, survives both web- and CLI-triggered runs, and keeps the subprocess self-contained). **MUST install the Schwab redaction factory on this surface** (the pipeline makes Schwab calls → pipeline.log could leak tokens/accountHash without it). NO schema.
- [ ] **1b — Per-step duration logging.** The runner already does `lease.step("name")` transitions + uses `time.monotonic()`; emit a per-step `elapsed=Ns` log line at each step boundary (and consider persisting per-step durations to `pipeline_runs` or a small `pipeline_step_timings` table for queryability — that part is a schema decision/OQ). Promote the existing `_walltime_elapsed` charts-warning pattern to ALL steps. This is the single change that would have answered the #96 question outright.
- [ ] **1c — (optional) yfinance call-timing audit.** Mirror `schwab_api_calls` for yfinance fetches (a lightweight timing log or a `marketdata_calls` table) so the dominant ~570s fetch cost is quantified per-step, not inferred. Schema if persisted; could start as log-only.

**Follow-on (linked, separate arc): pipeline PERF.** Once Arc 1 confirms the bottleneck, the likely lever is the #23-widened detect/observe yfinance load — cap/parallelize the exemplar + forward-observation fetches, cache exemplar bars across runs (#28/#29 exemplars are re-fetched every run; 34 exemplars w/ deep `period="max"` history is slow), or batch them. Gated on Arc 1's timing data — do NOT guess the fix before measuring.

---

## Arc 2 — General logging-system overhaul

**Goal:** one coherent, configurable, redaction-safe, retention-bounded logging system across web + CLI + pipeline — replacing today's per-surface ad-hoc setup.

- [ ] **2a — Centralized logging configuration.** A single `configure_logging(logs_dir, *, level, surface)` (or similar) that web (`app.py`), the CLI (`cli.py`), and the pipeline subprocess all call — consistent format, consistent rotation, a config-driven **log level** (none today), per-surface file routing (`web.log` / `pipeline.log` / `cli.log`). Subsumes Arc 1a's pipeline.log and the ad-hoc `finviz_api` level juggling.
- [ ] **2b — Rotation + RETENTION policy.** The 225MB logs dir with 83–97MB rotated files that never get cleaned is a real disk issue. Add a retention cap (max files / max age / max total size) to the rotating handler(s); decide the rotation trigger (size-based `RotatingFileHandler` vs the current dated rotation). Include a one-time cleanup of the existing oversized rotated files (operator-gated).
- [ ] **2c — Redaction coverage audit.** The Schwab `setLogRecordFactory` redaction is process-global but installed defensively per-call-site; audit that it covers EVERY log surface (esp. the new pipeline.log + CLI) and is installed early enough in each entrypoint. Consider promoting it to the centralized `configure_logging` so redaction is guaranteed on every surface by construction (not per-call-site). Extend the sentinel-leak audit test to the new surfaces.
- [ ] **2d — Run/request correlation.** The web has request-ids (`request_id` middleware); the spawned pipeline subprocess is a separate process with no correlation back to the triggering request/run. Thread the `pipeline_run_id` (and/or a correlation id) through the subprocess's log records so web.log ↔ pipeline.log ↔ `pipeline_runs` line up for a given run.
- [ ] **2e — Log-volume right-sizing.** Investigate why `web.log` reaches 53–97MB (likely DEBUG/per-request noise or a chatty dependency). Audit levels; demote noise; the dependency-logger control (the `finviz_api` pattern) generalized.
- [ ] **2f — Verbosity control knob.** A `[logging] level` (+ optional per-logger overrides) in `swing.config.toml` / user-config, surfaced consistently — so the operator can dial DEBUG for a diagnosis run without code edits.

---

## Arc 3 — Watchlist-thumbnail data-source divergence bug (XMAX) [BUG; observability-surfaced]

**Symptom (operator-reported 2026-06-08):** XMAX's dashboard watchlist **thumbnail shows only a handful of price points** (sparse angular line) while its expanded **`ticker_detail` chart is data-rich** ("last 207 bars", full candlesticks Aug-2025→May-2026).

**Investigation (orchestrator, 2026-06-08 — NOT a fix, characterized for the arc):**
- **Not stale-cache.** The `watchlist_row` render and the `ticker_detail` render are BOTH from run #96, BOTH `data_asof_date=2026-06-08` (thumbnail rendered 19:57:24 during the run; detail JIT-rendered at expand). svg sizes: thumbnail **6193 bytes** vs detail **216988 bytes** — a live data-volume divergence within the same run/day, not a stale render.
- **The data EXISTS.** Legacy `~/swing-data/prices-cache/XMAX.parquet` = **1260 clean rows** (no NaN) through 2026-06-08.
- **Divergent data sources between the two renders:** the thumbnail's bars come from `_bars_or_none(ticker)` → `ohlcv_cache.get_or_fetch(ticker, window_days=MIN_CALENDAR_DAYS_FOR_MA200)` ([runner.py:3022-3032/3083](../swing/pipeline/runner.py)); `render_watchlist_thumbnail_svg` then plots ALL passed bars ([charts.py:514](../swing/web/charts.py)), so a sparse line = the cache returned a TRUNCATED series. The `ticker_detail` path gets the full ~207 bars. (Note charts.py:273: "the thumbnail/line renderer does NOT route through this barrier" — the two paths already diverge.)
- **Prime suspect — Shape-A parallel-archive truncation.** XMAX has THREE parquet shapes: legacy `XMAX.parquet` (1260 rows, capitalized OHLCV), `XMAX.yfinance.parquet` (1261 rows, Shape-A), and **`XMAX.schwab_api.parquet` (only 15 rows, Shape-A)**. The 15-row Schwab Shape-A file is the likely culprit for a merge/resolution that truncates the series the thumbnail's `get_or_fetch` returns (the gotcha **#24** parallel-archive-freshness-desync + **#26** bar-content family). The detail path evidently resolves the full series; the thumbnail path does not.

- [ ] **3a — Root-cause the truncation.** Determine why `ohlcv_cache.get_or_fetch(XMAX, window_days=MIN_CALENDAR_DAYS_FOR_MA200)` returns a truncated series while the `ticker_detail` path returns ~207 bars in the SAME run — focus on the legacy-vs-Shape-A read resolution (`read_or_fetch_archive` vs `resolve_ohlcv_window`) and whether the 15-row `XMAX.schwab_api.parquet` shadows/caps the merged series. Likely affects ANY ticker with a partial Schwab Shape-A file (not just XMAX) — enumerate the blast radius.
- [ ] **3b — Unify (or reconcile) the thumbnail and detail bar sources** so a single ticker can't render rich in one surface and sparse in another for the same `data_asof_date`. Add a discriminating regression: a ticker with a partial Schwab Shape-A file + a full legacy/yfinance archive must yield the SAME bar count to both renderers.
- [ ] **3c — Cache-hash note (related, not the cause here):** `chart_renders.source_data_hash` is the STATIC literal `"step_charts_v1"` ([runner.py:3043](../swing/pipeline/runner.py)) — it does NOT encode the underlying data, so a thumbnail never invalidates on bar-count/data growth. Not the XMAX cause (that render was fresh), but a latent staleness footgun worth fixing alongside (key the hash on bar count + last asof_date).

---

## Arc 4 — Account-equity not reconciling: dashboard balance ≠ live Schwab balance [BUG + design gap]

**Symptom (operator-reported 2026-06-08):** the dashboard balance does not match the actual Schwab account balance, **even with all positions closed** (verified: 0 open trades — 1 `closed` + 15 `reviewed`).

**Investigation (orchestrator, 2026-06-08 — characterized + DB-verified, not fixed). The dashboard ACCOUNT tile reads `$1927` — which is NEITHER the Schwab snapshot NOR the live balance; there are THREE divergent equity numbers:**
- **(1) The ACCOUNT tile = a JOURNAL-COMPUTED ledger value (`$1927`).** The tile shows `current_equity` ([dashboard.py:922](../swing/web/view_models/dashboard.py); [trades/equity.py](../swing/trades/equity.py)) = `starting_equity + realized P&L + net cash_movements` — **NOT** the snapshot. DB-verified decomposition: `starting_equity $1200` (swing.config.toml) + `realized P&L −$73` (16 closed/reviewed trades, computed from fills) + `net cash +$800` (exactly 3 `cash_movements`, all deposits: $100 03-30, $100 04-29, $600 05-10) = **$1927**.
- **(2) The Schwab NLV snapshot = `$2027.44`** — `currentBalances.liquidationValue` ([mappers.py:210](../swing/integrations/schwab/mappers.py)), in `account_equity_snapshots` (source `schwab_api`, 06-08). It is used ONLY as the sizing/risk DENOMINATOR (`resolve_live_capital_denominator_dollars`, [metrics/equity_resolver.py](../swing/metrics/equity_resolver.py)) — it is **NOT** shown on the ACCOUNT tile.
- **(3) The live Schwab balance** — not surfaced anywhere live.
- **The gap = +$100.44** (Schwab NLV $2027.44 − ledger $1927). Schwab is HIGHER → **the journal ledger is UNDERCOUNTING by ~$100.**
- **When it fires / why "not reconciling".** The Schwab SNAPSHOT fires nightly (`_step_schwab_snapshot` [runner.py:946](../swing/pipeline/runner.py)) + on-demand (`swing schwab fetch --snapshot`), but it only feeds the denominator. **NOTHING reconciles the journal-computed tile equity against the broker** (snapshot or live) — the Phase-9/12 reconciliation is TRADE/fill-only. So the ledger silently drifts from Schwab with no check. (The denominator and the tile reading different equities is itself a coherence smell.)

**Root cause — CONFIRMED (operator, 2026-06-08): a missing recurring-deposit `cash_movement`.** The operator makes a **recurring $100/month deposit**; the journal's cash_movements end at 5/10 (the monthly $100s are recorded 3/30 + 4/29, plus a one-off $600 on 5/10), so the **~late-May (≈5/29–5/30) $100 monthly deposit was NEVER recorded** → the journal undercounts the broker by ~$100. **NOT interest/dividends** (operator-confirmed); the residual $0.44 is rounding / a minor P&L-fill detail.

**The systemic gap (why it silently drifted):** cash_movements aren't kept in sync with Schwab automatically. The machinery EXISTS but isn't wired to run/surface: manual entry via `swing journal cash --deposit` ([cli.py:1690](../swing/cli.py)); a Schwab-transactions→cash_movement ingestion mapper `map_transactions_to_cash_movement_candidates` ([mappers.py:543](../swing/integrations/schwab/mappers.py)); and a **`cash_movement_mismatch` discrepancy in the Schwab reconciliation** ([schwab_reconciliation.py:1040](../swing/trades/schwab_reconciliation.py)) that WOULD flag exactly this missing deposit — but none of it runs automatically or surfaces on the dashboard, so the drift sat uncaught and the tile silently trails the broker. **Immediate remediation:** record the missing deposit (`swing journal cash --deposit 100 --date <late-May>`) → the tile reconciles to ~$2027.

**Secondary (only relevant to the residual $0.44, if anything):** realized-P&L-from-fills fee/fill rounding; the `starting_equity $1200` baseline; NLV vs settled/unsettled timing.

- [x] **4a — DONE 2026-06-08: recorded the missing 5/28 recurring $100 deposit** (`cash_movement #4`, via `swing journal cash --deposit 100 --date 2026-05-28`, operator-confirmed date). Net cash $800→$900; the ACCOUNT tile now reconciles to **$2027** vs the Schwab NLV $2027.44 (residual **$0.44** = rounding / cent-level P&L-fill noise, not chased). **NOTE (feeds 4c):** recorded in ISO `2026-05-28`; the 3 prior rows are `M/D/YY` (Schwab-import-path artifact) — a `cash_movements` date-format inconsistency to normalize in 4c (cosmetic for the equity sum; matters for future cash-reconciliation date-matching/dedup). The SYSTEMIC fix so this can't silently recur is 4b.
- [ ] **4b — Wire up ROUTINE cash reconciliation (the actual systemic gap).** The pieces ALREADY exist — `cash_movement_mismatch` ([schwab_reconciliation.py:1040](../swing/trades/schwab_reconciliation.py)) + the Schwab-transactions→cash_movement ingestion mapper ([mappers.py:543](../swing/integrations/schwab/mappers.py)). Make them routine + SURFACED: auto-ingest Schwab cash transactions (deposits/withdrawals/interest/dividends) and/or run the `cash_movement_mismatch` reconciliation on a cadence (per pipeline, or a dashboard "reconcile balance" action) so a missing recurring deposit can't silently drift the displayed equity again. PLUS an equity-coherence check: the ACCOUNT tile (journal `current_equity`) and the sizing-denominator (Schwab NLV snapshot) currently read DIFFERENT equities — decide which is authoritative + flag the spread when it exceeds a tolerance.
- [ ] **4c — Cash-movement completeness + the cash-vs-NLV `kind` discriminator (schema).** Ingest Schwab interest/dividends/fees as `cash_movements` (so the ledger can't drift on uncredited cash); add a `kind` discriminator (or distinct columns) to `account_equity_snapshots` per the banked "cash-basis vs Net-Liq formalization" so each equity's basis is explicit (the risk floor uses `max($7500, actual)` per `[[project_capital_risk_floor]]`). **Schema change** (a migration) — the only Phase-16 item that likely touches schema.

---

## Sequencing (operator's call)

- **Arc 1** is the highest-leverage + smallest (1a + 1b alone would have answered the #96 question) — likely a focused executing-with-Codex, possibly folding 1a+1b into one cycle.
- **Arc 2** is broader (a real overhaul) — likely a full copowers cycle (brainstorm to settle the centralized-config shape + the retention/redaction/correlation OQs). Arc 1a's pipeline.log naturally folds INTO Arc 2a's centralized config; decide whether to ship Arc 1 standalone first (fast diagnosis) or design Arc 2 first and land 1 within it.
- The **perf follow-on** is gated on Arc 1's data.

*(Cross-refs: the Run #96 diagnosis is in this session's orchestrator transcript; the `#23` pool-widening + the data-integrity/deadlock/#16 arcs that shifted load to yfinance are recorded in `docs/phase3e-todo.md` §A + CLAUDE.md line-3. The Schwab redaction gotcha is in CLAUDE.md §Gotchas/Schwab.)*
