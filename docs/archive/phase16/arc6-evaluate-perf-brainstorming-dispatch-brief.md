# Brainstorming Dispatch Brief — Phase 16 / Arc 6: Evaluate-Step Performance (the Arc-1 perf follow-on)

**Arc:** Phase 16 / **Arc 6** — the pipeline-perf follow-on, now commissioned ON DATA (the Arc-1 instrument's purpose). Run #98 (cold nightly, 2026-06-09): **`evaluate` = 522s ≈ 91% of the 9.6-min wall** (detect 12s / observe 21s / charts 6s / schwab_orders 10s). Warm run #97: evaluate = 37s. The fix target is the evaluate step's market-data fetch path.
**Cycle stage:** `copowers:brainstorming` (produce a LOCKED design spec, Codex-converged). FULL copowers cycle — the design space is genuinely contested (batch vs bounded-parallel vs pre-warm; yfinance rate-limit risk; archive-integrity gotchas; a `swing/data/` carve-out).
**Branch-from:** main HEAD at worktree creation (currently `954995e3`; re-verify — the operator commits in parallel).
**Schema:** **NONE expected — v26 holds.** This is a latency fix; data content and schema are unchanged. If your design wants a table, STOP and flag.
**Deliverable:** a locked design spec at `docs/superpowers/specs/2026-06-10-evaluate-perf-design.md` + Codex convergence + `.copowers-findings.md` (prompts AND responses). Commit ONLY the spec doc.

---

## 1. Mandate (one line)

Make the nightly `evaluate` step's ~580 serial yfinance round-trips fast — without weakening any archive-integrity defense (F6 transient-empty, full-archive-return, #24 freshness, atomic writes) or tripping yfinance rate limits — and prove the win on a live nightly via the Arc-1 `pipeline_step_timings` instrument (baseline: run #98 evaluate=522s).

---

## 2. The diagnosis (orchestrator-grounded 2026-06-09/10 — verify, then design)

- **The call inventory** ([runner.py `_step_evaluate`](../swing/pipeline/runner.py), def @~1299): SPY @365d + **the candidate loop** (`for t in tickers: fetcher.get(t, lookback_days=400)` — run #98 had **63** candidates incl. open-trade union) + **the RS-universe loop** (`for t in universe.tickers: fetcher.get(t, lookback_days=120)` — **516 tickers**, verified via `load_universe`). Total ≈ **580 serial fetches**.
- **Each fetch:** `PriceFetcher.get` ([prices.py:26](../swing/prices.py)) → `read_or_fetch_archive` ([ohlcv_archive.py:204](../swing/data/ohlcv_archive.py)). On a new-session night EVERY archive is exactly 1 bar stale → the **incremental gap path** fires per ticker: `_yf_download_window(ticker, start=latest_stored+1, end=today)` = one `yf.download(..., threads=False)` HTTP round-trip each. **522s ÷ 580 ≈ 0.9s/call — serial round-trip latency, not data volume.**
- **The weekly storm:** `needs_full_refresh` fires per ticker when `(today - last_full_refresh).days >= 7` → a FULL `archive_history_days=1260`-trading-day re-download (`_calendar_window_for_trading_days`). 516+ full downloads land on whatever night each ticker's 7-day clock expires — un-staggered.
- Cache layer notes: the Schwab market-data ladder covers QUOTES (PriceCache), not these bars; the `OhlcvCache.set_ladder_bars_fetcher` hook (runner.py:~419-438) routes through `read_or_fetch_archive` too. The candidate-loop and universe-loop both go through the SAME `fetcher.get`.

---

## 3. Candidate approaches (weigh these + any better one; pick + justify; benchmark before locking)

- **(A) Batched gap pre-warm (orchestrator's lean — smallest blast radius).** A new `warm_archives_batch(tickers, ...)` that `_step_evaluate` calls ONCE before its loops: one (or a few chunked) **multi-ticker `yf.download([...], threads=False)`** call(s) fetching the shared gap window for all ~580 tickers, writing each ticker's slice through the EXISTING per-ticker archive-write path (atomic write, F6 empty-guard per ticker). The per-ticker loops then hit fresh archives → zero fetches. `read_or_fetch_archive` semantics stay UNTOUCHED for every other consumer (charts, daily-mgmt warm, detect/observe, web) — they just benefit when evaluate pre-warmed. Risks to resolve: yf multi-ticker response shape (MultiIndex columns — the `group_by` gotcha), per-ticker-missing-in-batch handling (must NOT blank that ticker's archive — F6; must fall back to the serial path or skip-warn), chunk size vs rate limits, and tickers whose gap differs (mixed staleness) vs a uniform window.
- **(B) Bounded-parallel per-ticker fetches.** A small executor (4-8 workers) around the existing per-ticker `read_or_fetch_archive` calls. Simpler response handling (per-ticker isolation free), but: yfinance rate-limit exposure (the gotcha exists because parallel hammering tripped limits before), thread-safety of the archive write path (atomic per-ticker writes are probably fine — verify `_write_archive_atomic` under concurrency, same-ticker exclusion), and the win caps at the worker count.
- **(C) Hybrid:** batch for the uniform 1-bar gap majority; serial fallback for stragglers/full-refreshes.
- **Weekly-storm fix (orthogonal, include it):** stagger `needs_full_refresh` (e.g. hash(ticker) % 7 day-bucket, or cap full-refreshes per run with carry-over) so ≤ ~1/7 of the universe full-refreshes on any night.
- **OUT unless flagged:** reducing the 516-ticker universe refresh scope or tolerating stale universe bars — that's a METHODOLOGY change (RS-rank inputs), not a perf fix; if the design concludes it's the only real lever, STOP and flag for the operator/research-director rather than deciding it.

**A benchmark task belongs IN the cycle** (executing phase): measure the chosen mechanism against the real universe (a bounded live probe or a recorded harness) before declaring the target met. Set the acceptance target: **evaluate ≤ 90s on a cold nightly** (vs 522s baseline; stretch ≤ 60s), verified via `pipeline_step_timings` on the operator-gate run.

---

## 4. Locks / invariants (do not weaken — these are the arc's hard walls)

- **F6 transient-empty:** a batch response missing ticker T must NOT overwrite T's archive or meta — retain existing, leave meta stale, next call retries. Per-ticker enforcement INSIDE whatever batch path is built.
- **Full-archive-return contract:** cache hooks return the FULL archive; consumers slice. The pre-warm writes full/merged archives, never window-truncated ones.
- **Atomic writes:** the existing `_write_archive_atomic` (same-dir temp + `os.replace`, Windows same-fs gotcha) stays the only archive write mechanism.
- **#24 parallel-archive freshness + the bad-bar/dedup `write_window keep='last'` semantics:** unchanged; the legacy `{T}.parquet` shape is the one being warmed (NOT the Shape-A sidecars — do not touch the Arc-3/XMAX territory).
- **yfinance gotchas:** `threads=False` on `yf.download` (incl. batch calls); `group_by='column'` MultiIndex squeeze; the partial-bar strip is the CONSUMER's job (evaluate already handles session anchoring via `_resolve_asof`) — the warm must not introduce in-progress bars (fetch `end=today` mirrors the existing behavior; verify the boundary).
- **Phase isolation — EXPLICIT CARVE-OUT REQUIRED:** `swing/data/` is read-only by default; this arc's spec must scope the carve-out explicitly (the historical pattern: 3c/3d/5/6/7 each named theirs): expected loci = `swing/data/ohlcv_archive.py` (the new batch/stagger internals), `swing/prices.py` (if `PriceFetcher` grows a batch entry), `swing/pipeline/runner.py` (the `_step_evaluate` pre-warm call). NO repo/schema/model changes. `swing/trades/` untouched.
- **No behavior change to data content** — same bars, same archives, same buckets; ONLY latency. A parity test (same evaluate outputs pre/post on a fixed fixture set) is in scope.
- Schema NONE (v26). DB-outside-Drive. Zero `Co-Authored-By`.

---

## 5. Open questions for the operator (brainstorm surfaces + resolves)

- **OQ-1 — mechanism:** A (batched pre-warm) vs B (bounded-parallel) vs C (hybrid) — recommend with the rate-limit analysis + the response-shape risk weighed. (Orchestrator lean: A or C; B alone caps low and pokes the rate-limit bear.)
- **OQ-2 — chunk size + pacing for batch calls** (one 580-ticker call vs N chunks with spacing): what does yfinance tolerate today? Ground it.
- **OQ-3 — the weekly-storm stagger policy** (hash-bucket vs per-run cap) + whether the full-refresh can ALSO be batched.
- **OQ-4 — the acceptance target** (proposed: cold-nightly evaluate ≤ 90s, stretch 60s) + the benchmark mechanism inside the cycle.
- **OQ-5 — failure-mode posture:** if the batch path fails wholesale (rate-limited, network), does evaluate fall back to the serial path (slow but correct — likely YES) and how is that audited (#27 warning)?

---

## 6. copowers process (binding)

- Run `copowers:brainstorming` (explore the §5 OQs WITH the operator → adversarial Codex loop **to convergence**, `NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED).
- **Codex transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows; tell Codex not to run git.
- Persist BOTH prompts AND responses to gitignored `.copowers-findings.md`. Commit ONLY the spec doc; conventional commits; final `-m` paragraph plain prose; trailers `[]`.
- **Return a report:** the spec path; the resolved §5 OQs (mechanism + chunking + stagger + target + fallback); the Codex verdict (rounds + final line); flagged items for writing-plans. Then STOP — writing-plans is a separate commission after orchestrator QA.

---

## 7. What this arc is NOT

NOT a methodology change (universe scope/staleness stays as-is unless explicitly flagged + operator-decided). NOT the XMAX/Shape-A archive work (Arc 3). NOT 1c (a `marketdata_calls` audit table — if the design wants call-level metrics, log-only is fine; no schema). NOT a Schwab-bars ladder extension (quotes-only today; bars stay yfinance). NOT detect/observe/charts optimization (they're 12-21s — immaterial next to evaluate).
