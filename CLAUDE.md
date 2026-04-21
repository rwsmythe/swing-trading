# Swing Trading — Claude Code Context

Personal swing-trading tool (Disciplined Swing Trader + Minervini SEPA). Active ground-up refactor. Phase 3d shipped (SMA-aware advisories). End-to-end walkthrough validated the full operator loop; 9+ post-walkthrough fixes landed on `main` (library-API regressions, dashboard/pipeline UX). **504 fast tests green.** Phase 3e backlog in `docs/phase3e-todo.md`. Daily routine in `docs/cycle-checklist.md`.

## Quick Start

```bash
pip install -e ".[dev,web]"
swing --help                         # CLI: trade, journal, pipeline, web, finviz, etc.
swing web                            # FastAPI + HTMX dashboard on 127.0.0.1:8080
python -m pytest -m "not slow" -q    # fast suite (499 tests, ~15s)
python -m pytest -m slow             # pipeline/yfinance e2e (minutes, needs network)
ruff check swing/
```

**Windows PATH for `swing` CLI:** `pip install -e` places the `swing.exe` entry point in `%APPDATA%\Python\Python314\Scripts\` (user install, not `C:\Python314\Scripts`). Add that dir to the user PATH permanently via System Properties, or per-session: `$env:PATH = "$env:APPDATA\Python\Python314\Scripts;$env:PATH"`.

**Finviz inbox:** `data/finviz-inbox/` (configured in `swing.config.toml`). Save exports as `finvizDDMmmYYYY.csv`. Validator requires 13 columns: `No., Ticker, Sector, Industry, Country, Price, Change, Average Volume, Relative Volume, Average True Range, 52-Week High, 52-Week Low, Market Cap`. Missing columns → CSV moved to `data/finviz-inbox/rejected/` with a sidecar `.rejected-reasons.json`. Pipeline outputs go to `exports/<action_session_date>/` (briefing.md + briefing.html + charts/).

**Pipeline lease-acquisition wait** (`web.pipeline_lease_wait_seconds`, default 5s): how long POST `/pipeline/run` waits for the spawned subprocess to insert its `pipeline_runs` row. Python 3.14 cold-start + heavy imports on Windows regularly cross 2s; bump if you see false "did not acquire lease" errors on a slow box.

## Architecture

`swing/` — application package:
- `data/` — SQLite schema (`migrations/*.sql`), dataclass models, repo functions
- `pipeline/` — nightly orchestrator, lease fencing, finviz CSV select+validate, step runners
- `trades/` — entry/exit/stop_adjust services, advisory rules, equity math
- `recommendations/` — `compute_shares` / `SizingResult` (position sizing)
- `evaluation/` — A+ criteria, bucket rules, date semantics (`action_session_for_run`)
- `web/` — FastAPI + HTMX (`app.py`, `routes/`, `view_models/`, `templates/`, `middleware/`, `price_cache.py`)
- `cli.py` — click-based `swing` CLI entry point

`tests/` mirrors `swing/`. `docs/superpowers/specs/` and `/plans/` hold per-phase design docs.

## Invariants

- **DB location:** `%USERPROFILE%/swing-data/swing.db` — **outside** the Drive dir (hard invariant; Drive syncing corrupts SQLite).
- **Phase isolation:** during Phase 3 work, `swing/trades/` and `swing/data/` are consumed read-only unless the current-phase spec explicitly scopes a Phase 2 carve-out (3c touched `update_stop_with_event`; 3d touched `advisory.py`).
- **Current baseline:** 504 fast tests green on `main`.

## Conventions

- **Branch:** all work on `main` (established for this project).
- **Commits:** conventional (`feat(web):`, `fix(web):`, `refactor(...)`, `test(...)`). **No Claude co-author footer, no `--no-verify`.**
- **TDD:** write failing test → see fail → minimal implementation → see pass → commit, per task.
- **copowers workflow:** `copowers:brainstorming` → `copowers:writing-plans` → `copowers:executing-plans` (wraps `subagent-driven-development`). Each adds adversarial Codex MCP review (2–5 rounds) before approval. Session state in `.copowers-session-*.json` at project root.
- **Starlette 1.0 signature:** `TemplateResponse(request, "name", {...}, status_code=...)`.
- **TestClient lifespan:** tests touching `app.state.price_fetch_executor` MUST use `with TestClient(app) as client:` (enters lifespan).

## Windows + gitbash

- Drive path has a space — always quote `"c:/Users/rwsmy/My Drive/Swing Trading"`.
- Unix shell syntax (`/dev/null`, not `NUL`); forward slashes in paths work in Python.
- Python 3.14 on this machine; `pyproject.toml` targets `>=3.11`.
- CRLF warnings from git are cosmetic — ignore.

## Gotchas

- **yfinance rate-limits.** Use `threads=False` on `yf.download()` ONLY. `yf.Ticker(t).history()` does NOT accept `threads=` and raises `TypeError: got an unexpected keyword argument 'threads'` on yfinance >= 1.2. Concurrency for `Ticker.history()` is bounded by the app-level executor; `PriceCache` + `OhlcvCache` sliding-window breakers are the real backpressure.
- **Test-count drift in plan docs.** Plans show stale expected counts — trust `pytest` output.
- **The auto-memory at `~/.claude/projects/c--.../memory/`** can go stale. Verify `project_refactor_intent.md` against current git log before assuming refactor is out-of-scope.
- **HTMX 4xx fragments need an explicit config override.** HTMX 2.x default is `{code:"[45]..",swap:false,error:true}` — 4xx responses fire the error event but don't swap. `base.html.j2` contains a `htmx.config.responseHandling` override that enables 4xx swapping; preserve it if you touch the base layout. TestClient-based tests won't catch a regression (they assert response body, not DOM state).
- **Starlette middleware is LIFO.** `add_middleware` call order is the REVERSE of request execution order — later calls become more-outer. Security-critical middleware (OriginGuard strict-mode, request-id stamping) must be added LAST so it wraps everything inside. A body-size check added after OriginGuard but before RequestId would fire 413 before OriginGuard's 403, silently weakening strict mode.
- **`os.replace` requires same filesystem.** On Windows with Drive-synced paths + `$TMP` on a different volume, `os.replace(tmp, final)` raises `OSError: [Errno 18] Invalid cross-device link`. For atomic-replace flows: create temp files in the destination directory (`tempfile.NamedTemporaryFile(dir=<dest_dir>, ...)`). Never use `shutil.move` expecting overwrite on Windows — it fails when the destination exists.
- **yfinance `history(interval="1d")` includes the in-progress bar during market hours.** The last row is today's PARTIAL session until the next session rolls over. If you compute a rolling-mean SMA or a "previous close" directly off `df.tail()`, you're sampling a partial intraday close — a "close below MA" rule turns back into an intraday rule. Strip it: `if df.index[-1].date() >= session: df = df.iloc[:-1]` where `session = action_session_for_run(datetime.now())`. Use the exchange-session helper, NOT `date.today()` — HST lags ET by 5h, so local midnight would incorrectly preserve today's partial bar for hours.
- **`base.html.j2` is shared — new `vm.foo` field requires adding to EVERY base-layout VM.** Every page that `{% extends "base.html.j2" %}` has a VM rendered as `vm` in the template context. If the base layout starts dereferencing a new field (banner flag, session date, etc.), EVERY base-layout VM must gain that field (with a safe default) or Jinja 500s unrelated routes with `UndefinedError`. Current set: `DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`. Phase 3c hit this with `price_source_degraded` initially and caught it during adversarial review; Phase 3d hits it again with `ohlcv_source_degraded`. Same fix pattern each time.
- **Cache + executor race: workers must not write to shared state when the request thread cancels on deadline miss.** `Future.cancel()` is a no-op on a running worker. If the worker writes to `cache._store` from inside itself, a late-completing worker will poison the cache with a bundle the request thread already gave up on. Pattern: worker returns a pure value; request thread writes to `_store` ONLY for futures that completed in-deadline (`wait(..., timeout=deadline)` → iterate `done`, not `pending`). `OhlcvCache` follows this; future caches should too.
- **Weather lookup in read-only UIs must NOT query by `action_session`.** Weather is stored keyed by `data_asof_date` (last completed NYSE session); `action_session` is forward-looking (next session). On Sunday-evening → Monday-prep workflow (or any weekend/holiday gap) the query silently returns `None` → UI renders STALE despite a fresh weather row existing. Use `swing.data.repos.weather.get_latest(conn, ticker=...)` which returns the most recent record by `run_ts` regardless of date. The pipeline's own briefing generator uses `data_asof`; read-only UIs should use `get_latest`.
- **OHLCV fetch scope = open-trade tickers ONLY.** Advisories (trail-MA, exit-below-MA) only fire on open positions; watchlist rows never consume SMA data. Fetching OHLCV for watchlist tickers burns yfinance quota on every render and trips the `OhlcvCache` sliding-window breaker under normal load. `build_dashboard` computes `ohlcv_tickers = sorted({t.ticker for t in open_trades})` — do NOT union with watchlist or `active_tickers`. With zero open trades, skip the fetch entirely (guarded by `if ohlcv_cache is not None and ohlcv_tickers`).
- **yfinance `group_by='column'` now returns a MultiIndex column** (`Price × Ticker`) even for single-ticker calls. `df["Close"]` is a DataFrame, not a Series — `float(iloc[-1])` raises `TypeError: float() argument must be a string or a real number, not 'Series'`. Squeeze defensively: `close = df["Close"]; if hasattr(close, "ndim") and close.ndim == 2: close = close.iloc[:, 0]`. This and the `Ticker.history()` `threads` regression are examples of the same failure mode: pip-installed dependency updates silently break integration points that were working last quarter.
- **`exchange_calendars.is_open_at_time` requires `pd.Timestamp`**, not `datetime.datetime`. Passing a plain datetime raises `TypeError: \`timestamp\` expected to receive type pd.Timestamp`. The prior `market_hours_now()` caught all exceptions silently and returned `False`, permanently routing PriceCache to the last-close fallback during live trading hours. Wrap: `pd.Timestamp(datetime.now(timezone.utc))`. Same failure class as the yfinance API regressions above — when you catch broad exceptions around a dependency call, log them instead of silently returning a degraded default.
- **`PriceCache._last_close` only sees tickers in today's `candidates` table.** Open-trade tickers that rotate OUT of the finviz CSV get no fresh candidate row, so the after-hours fallback returns the close from whenever they were last in finviz (potentially days old). `_step_evaluate` unions `list_open_trades` into its fetch loop and writes them as `bucket='excluded'` with `notes='open position'` so the close stays fresh every run. If you add a new "priced" UI surface, verify its tickers actually appear in `candidates` — otherwise the fallback lies silently.
- **Queries ordered by `started_ts DESC` on `pipeline_runs` mask prior completes mid-run.** A new run with `finished_ts IS NULL` wins the ORDER BY and surfaces NULL where callers expect the last-known-good timestamp (dashboard "Last pipeline" rendered "never" the entire time a run was in flight). Two-read pattern: most-recent COMPLETED row's `finished_ts` for "when did we last have good data?", separately most-recent-started row's `state` for "what's happening right now?"
