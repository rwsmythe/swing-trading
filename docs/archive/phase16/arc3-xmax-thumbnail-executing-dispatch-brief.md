# Focused-Executing Dispatch Brief — Phase 16 / Arc 3: Watchlist-Thumbnail Data-Source Divergence (XMAX)

**Arc:** Phase 16 / **Arc 3** — the observability-surfaced bug: XMAX's watchlist THUMBNAIL rendered ~15 sparse points while the `ticker_detail` chart rendered ~207 rich bars, SAME run (#96) / same `data_asof_date`. Registered with the original characterization in [`docs/phase16-todo.md`](phase16-todo.md) §Arc 3 (3a root-cause · 3b unify · 3c the static cache hash).
**Cycle stage:** **FOCUSED executing-with-Codex with a STOP-GATE:** Task 1 is a root-cause CONFIRMATION (a reproduction harness); if the confirmed cause materially diverges from the §3 hypothesis space, STOP and return for re-commissioning instead of improvising a fix.
**Branch-from:** main HEAD at worktree creation (currently `a9a9a158`; re-verify — the operator commits in parallel).
**Schema:** **NONE — v28 holds.** The 3c fix changes the VALUE written to the existing `chart_renders.source_data_hash` column — no migration.
**Deliverable:** the fix shipped TDD + Codex-converged + `.copowers-findings.md` (prompts AND responses). Suite baseline: **7821**.

---

## 1. Mandate (one line)

Root-cause (confirm), then fix, the thumbnail-vs-detail bar-count divergence so a single ticker cannot render rich in one surface and sparse in another for the same `data_asof_date` — with a discriminating regression (a ticker with a partial Schwab Shape-A file + a full legacy archive yields the SAME bar count to BOTH renderers) and the 3c cache-hash fix (key it on bar count + last asof_date so thumbnails invalidate on data growth).

---

## 2. Evidence (orchestrator-grounded; the 06-08 characterization UPDATED 2026-06-11)

- **The three XMAX parquet shapes TODAY:** legacy `XMAX.parquet` = 1260 rows (fresh through 06-10, Arc-6-warmed); `XMAX.yfinance.parquet` = 1263 (Shape-A); **`XMAX.schwab_api.parquet` = 16 rows (GREW from 15 — something still writes it; last 06-09).**
- **NEW (2026-06-11, orchestrator live probe): the truncation does NOT reproduce in the WEB process** — a fresh `OhlcvCache(cfg).get_or_fetch(ticker='XMAX', window_days=300)` returns the FULL **207 rows**. The 06-08 sparse render happened in the PIPELINE process (`_step_charts` → the thumbnail's `_bars_or_none` → `ohlcv_cache.get_or_fetch(..., window_days=MIN_CALENDAR_DAYS_FOR_MA200)`), where `_install_pipeline_marketdata_caches` (runner.py ~313-438) installs the **Schwab market-data ladder hooks** (`set_ladder_bars_fetcher`, the OQ-C audit conn, etc.) on the pipeline's OhlcvCache. The web `ticker_detail` render has NO ladder. **The divergence is process/configuration-dependent — the prime suspect is the pipeline-installed ladder path** (its bars hook / `_fetch_bars_window` slicing / the Shape-A `resolve_ohlcv_window` precedence where `schwab_api=0` beats `yfinance=1` per `_SOURCE_PRECEDENCE_MARKET_DATA`), NOT the bare web cache.
- **3c is LOAD-BEARING for the operator-visible symptom:** `source_data_hash="step_charts_v1"` (a STATIC literal, runner.py:3415) means a cached sparse thumbnail is NEVER invalidated by data growth — the sparse XMAX render from #96 may still be the artifact being SERVED today even if later runs would render it correctly. The fix must both repair the source path AND make the cache key honest.
- **Incidental observation (check, don't assume):** a direct `resolve_ohlcv_window('XMAX', start=<date>, end=<date>)` call raises `TypeError: '<=' not supported between 'datetime.date' and 'str'` (the parquet `asof_date` is str). Verify its REAL callers' arg types — if they pass ISO strings it's a doc/signature sharp edge, not a bug; if any caller passes dates, that's a latent defect to note (fix only if it's in this arc's blast path).

---

## 3. The hypothesis space (Task 1 confirms WHICH; STOP if none fits)

(a) The pipeline ladder's bars hook returns/slices a Schwab-sourced window (~10-16 daily bars — cf. the Schwab `price_history` short-window family) and the thumbnail consumed it directly, violating the **full-archive-return contract** ("cache hooks must return the FULL archive; consumers slice" — the standing gotcha). (b) The Shape-A `resolve_ohlcv_window` per-date precedence (schwab_api=0 wins) interacts with a coverage/freshness gate so the 16-row schwab file caps the merged window in the ladder path. (c) The stale-cached-render variant: the source paths are now fine and the 06-08 symptom persists only via the static `source_data_hash` (pure 3c). **Task 1 must discriminate among these with a reproduction harness that mirrors the PIPELINE process configuration** (OhlcvCache + the ladder hooks installed the way `_install_pipeline_marketdata_caches` does, fixtures mirroring the three real XMAX shapes — derive from the REAL files' schemas, the synthetic-vs-real drift gotcha). Whichever confirms, the fix direction is the SAME contract: **hooks/resolution return the full merged series; consumers slice; the thumbnail and detail paths converge on identical bar counts.**

---

## 4. Scope + locks

- **3a:** the reproduction harness + a root-cause memo in the return report (file:line of the truncating locus) + the **blast radius enumerated** (count the tickers with a partial `*.schwab_api.parquet` in the real cache — read-only — and state whether each is exposed).
- **3b:** the fix + the discriminating regression (partial Schwab Shape-A + full legacy → SAME bar count to `render_watchlist_thumbnail_svg`'s input and the `ticker_detail` path's input). Do NOT delete/stop-writing the Schwab Shape-A files unless Task 1 PROVES that's the only sound fix (that touches the ladder's write side — flag first). Preserve Shape-A persistence semantics (`write_window`, per-source precedence) — the fix belongs on the READ/resolution side per the full-archive-return contract.
- **3c:** key `source_data_hash` on (bar count + last `asof_date`) (or strictly better); a regression: a thumbnail rendered sparse then re-rendered after data growth gets a DIFFERENT hash → re-render. NO migration (value-only change). Note: existing cached `chart_renders` rows with the old static hash will all re-render once — acceptable, say so in the report.
- **Locks:** NO schema (v28). `swing/trades/` + `swing/data/migrations/` untouched. The Arc-6 warm + Arc-8 barrier in `ohlcv_archive.py` untouched unless the root cause lives there (flag if so). The Schwab quote ladder (PriceCache side) untouched. Suite baseline 7821; the 3 banked `-n0` order-dependent schwab-route flakes are pre-existing (todo §Arc-2-Slice-2 note).
- **Operator gate (post-merge, surface in the return):** the next pipeline run's XMAX (or any blast-radius ticker's) thumbnail renders data-rich — the operator eyeballs the watchlist page once; plus the orchestrator verifies the re-render happened (a fresh `chart_renders` hash).

---

## 5. Execution + copowers process (binding)

- **TDD, green-per-commit** (failing test → SEE fail → minimal impl → SEE pass → ruff → commit; conventional; NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose; trailers `[]`). Task 1 (reproduction) FIRST; STOP at the gate if the root cause diverges from §3.
- **Codex after all tasks, to convergence** (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED) — ask it to probe: the reproduction's fidelity to the real pipeline configuration, whether the fix holds for ALL blast-radius tickers (not just XMAX), the 3c hash's collision behavior, and any consumer depending on the old sliced-hook behavior.
- **Transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows; tell Codex not to run git; capture output to FILES (no head-truncated pipes). Persist BOTH prompts AND responses to gitignored `.copowers-findings.md`. Scrutinize rebuttals against disk.
- **Full fast suite + ruff ON YOUR FINAL HEAD** (actual count).

---

## 6. Return report (then STOP — do NOT merge)

The root-cause memo (which §3 hypothesis confirmed; file:line; the blast-radius count + exposure); the commit SHAs + messages; the suite result (actual count) + ruff; the 3c hash design + the one-time re-render note; confirmation of the locks; the Codex verdict (rounds + final line); any deviation with justification; the operator-gate note.
