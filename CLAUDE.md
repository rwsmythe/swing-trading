# Swing Trading — Claude Code Context

Personal swing-trading tool (Disciplined Swing Trader + Minervini SEPA). Active ground-up refactor. Phase 3c shipped (commit `3e934ef`, 444 fast tests). Phase 3d (SMA-aware advisories) plan approved via 8 Codex adversarial rounds (spec `c3d65df` + plan `2706c8f`); awaiting execution.

## Quick Start

```bash
pip install -e ".[dev,web]"
swing --help                         # CLI: trade, journal, pipeline, web, finviz, etc.
swing web                            # FastAPI + HTMX dashboard on 127.0.0.1:8080
python -m pytest -m "not slow" -q    # fast suite (~444 tests, ~15s)
python -m pytest -m slow             # pipeline/yfinance e2e (minutes, needs network)
ruff check swing/
```

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
- **Phase isolation:** during Phase 3 work, `swing/trades/` and `swing/data/` are consumed read-only unless the current-phase spec explicitly scopes a Phase 2 carve-out (3c touched `update_stop_with_event`; 3d will touch `advisory.py`).
- **Current baseline:** 444 fast tests green (end of Phase 3c) must stay green through 3d changes.

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

- **yfinance rate-limits.** Use `threads=False` in library calls; the app-level executor cap + `PriceCache` circuit breaker (`swing/web/price_cache.py`) are the real backpressure mechanisms.
- **Test-count drift in plan docs.** Plans show stale expected counts — trust `pytest` output.
- **The auto-memory at `~/.claude/projects/c--.../memory/`** can go stale. Verify `project_refactor_intent.md` against current git log before assuming refactor is out-of-scope.
- **HTMX 4xx fragments need an explicit config override.** HTMX 2.x default is `{code:"[45]..",swap:false,error:true}` — 4xx responses fire the error event but don't swap. `base.html.j2` contains a `htmx.config.responseHandling` override that enables 4xx swapping; preserve it if you touch the base layout. TestClient-based tests won't catch a regression (they assert response body, not DOM state).
- **Starlette middleware is LIFO.** `add_middleware` call order is the REVERSE of request execution order — later calls become more-outer. Security-critical middleware (OriginGuard strict-mode, request-id stamping) must be added LAST so it wraps everything inside. A body-size check added after OriginGuard but before RequestId would fire 413 before OriginGuard's 403, silently weakening strict mode.
- **`os.replace` requires same filesystem.** On Windows with Drive-synced paths + `$TMP` on a different volume, `os.replace(tmp, final)` raises `OSError: [Errno 18] Invalid cross-device link`. For atomic-replace flows: create temp files in the destination directory (`tempfile.NamedTemporaryFile(dir=<dest_dir>, ...)`). Never use `shutil.move` expecting overwrite on Windows — it fails when the destination exists.
- **yfinance `history(interval="1d")` includes the in-progress bar during market hours.** The last row is today's PARTIAL session until the next session rolls over. If you compute a rolling-mean SMA or a "previous close" directly off `df.tail()`, you're sampling a partial intraday close — a "close below MA" rule turns back into an intraday rule. Strip it: `if df.index[-1].date() >= session: df = df.iloc[:-1]` where `session = action_session_for_run(datetime.now())`. Use the exchange-session helper, NOT `date.today()` — HST lags ET by 5h, so local midnight would incorrectly preserve today's partial bar for hours.
- **`base.html.j2` is shared — new `vm.foo` field requires adding to EVERY base-layout VM.** Every page that `{% extends "base.html.j2" %}` has a VM rendered as `vm` in the template context. If the base layout starts dereferencing a new field (banner flag, session date, etc.), EVERY base-layout VM must gain that field (with a safe default) or Jinja 500s unrelated routes with `UndefinedError`. Current set: `DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`. Phase 3c hit this with `price_source_degraded` initially and caught it during adversarial review; Phase 3d hits it again with `ohlcv_source_degraded`. Same fix pattern each time.
- **Cache + executor race: workers must not write to shared state when the request thread cancels on deadline miss.** `Future.cancel()` is a no-op on a running worker. If the worker writes to `cache._store` from inside itself, a late-completing worker will poison the cache with a bundle the request thread already gave up on. Pattern: worker returns a pure value; request thread writes to `_store` ONLY for futures that completed in-deadline (`wait(..., timeout=deadline)` → iterate `done`, not `pending`). `OhlcvCache` follows this; future caches should too.
