# Phase 18 Arc 18-C — yfinance call audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Read `CLAUDE.md` (gotchas) + `docs/phase18-arc-c-dispatch-brief.md` first; re-ground every file:line anchor against live code (line numbers drift).

**Goal:** Add a `yfinance_calls` audit table (migration `0030`, schema v29 → v30) + a recording service mirroring `schwab_api_calls` / `swing/integrations/schwab/audit_service.py`, so that yfinance fetches become observable (timings, errors, empties, rows, run-linkage) to feed 18-D (RD research monitor) + 18-E (tool-health monitor). **Purely additive observability** — it records AROUND the existing `yf.download` calls and changes nothing about what they fetch, their kwargs, their result, or how the measurement consumes them.

**Architecture (settled — NO brainstorm).** Mirror the Schwab three-piece transactional discipline: a `swing/data/repos/yfinance_calls.py` repo (caller-controlled tx; `insert_in_flight` → `update_call_outcome`; UPDATE-in-place, never `INSERT OR REPLACE`), a `swing/data/yfinance_audit.py` service (`record_call_start` / `record_call_finish`; owns `BEGIN IMMEDIATE`; rejects caller-held tx; a yfinance-specific `_YF_AUDIT_WRITE_LOCK` held ONLY around the sub-ms start/finish tx — never across `yf.download` — plus a 100ms busy-timeout, so same-process audits serialize deterministically, there is no fetch-time convoy, and cross-process contention is bounded best-effort; carries the shared `_record_yf_download` chokepoint helper), a `YfinanceCall` dataclass in `swing/data/models.py` with `__post_init__` frozenset validators, and the instrumentation **around the RAW `yf.download` call at each of the 4 production sites**. Instrumentation does NOT wrap whole functions — it brackets the raw `yf.download` so empty/error are classified at the call boundary BEFORE any caller-side conversion to exceptions (Codex R1 MAJOR). The 4 sites do NOT take a `conn` (their many consumers don't thread one) — they read a **lock-guarded process-global audit context** (`db_path` + `pipeline_run_id` + `surface`) with an explicit **base-vs-scope API** (Codex R2/R5 MAJOR — a persistent BASE set at web/CLI startup, plus a nested `yfinance_audit_scope(...)` context-manager with LIFO token-restore + a single-active-non-base-scope guard, so an in-process pipeline scope under a web base restores the base on exit rather than clobbering it). The context is set by the entry points that DO have it (the pipeline runner; the archive-reaching CLI commands `eval`/`weather`/`pattern label`; the web app startup), exactly mirroring the established `swing/log_correlation.py` process-global pattern (chosen there, and here, BECAUSE the warm runs `threads=True` and a `ContextVar` would silently drop on worker threads). Absent context (unit tests with no seam) = recording no-ops. **`swing/data/ohlcv_archive.py` stays DB-free at module import** (Codex R2 MAJOR): it imports only the DB-free `yfinance_audit_context` at module level; the DB-aware `_record_yf_download` recorder is LAZILY imported inside the chokepoint, only when a context is active.

**Tech Stack:** Python 3.14, sqlite3, pytest. **NO new dependency** (yfinance + sqlite already declared; R1 `requests` does NOT ride this arc — see §R1). **NO `pyproject` touch.** New schema/migration (the §3-tripwire crossing this brief authorizes). Touches `swing/data/` (the authorized carve-out: new table + repo + model + service + a new `swing/data/yfinance_audit_context.py` + the `ohlcv_archive.py` chokepoint instrumentation), `swing/patterns/labeling_bars.py`, `swing/web/price_cache.py` + `swing/web/app.py`, `swing/pipeline/runner.py`, `swing/cli.py` (set the context), `swing/data/db.py` (backup gate). NO `swing/trades/` touch.

---

## Background — re-grounding (verified on disk at branch start, base `ad8138b6`)

### The `yf.download` enumeration (FIRST DELIVERABLE — audit-to-confirm, #27)

`grep -rn "yf\.download(" swing/` returns exactly **4 direct `yf.download` invocation sites in 4 files** (every `yf.download` in `swing/` is an actual call; no commented-out call sites), covering 5+ runtime caller paths (each chokepoint fans out to several callers):

| # | site (file:line) | shape | runtime path | disposition | reason |
|---|------------------|-------|--------------|-------------|--------|
| 1 | `swing/data/ohlcv_archive.py:257` `_yf_download_window` | single-ticker daily window (`threads=False`) | pipeline warm-miss serial loops + CLI + web archive reads | **INSTRUMENT — `call_type='download_single'`** | THE single chokepoint; reached by `read_or_fetch_archive` (gap + full-refresh branches) which fans out to the runner, `swing/web/app.py`, `swing/web/ohlcv_cache.py`, `swing/prices.py`, `swing/pipeline/ohlcv.py`. Instrumentation lives AT the chokepoint, not the callers, so all consumers are audited with one bracket. |
| 2 | `swing/data/ohlcv_archive.py:503` `_fetch_chunk` | multi-ticker batch (`threads=True`, `group_by='ticker'`) | pipeline `_step_evaluate` warm (`warm_archives_batch` → `_warm_one_window` → `_fetch_chunk`) | **INSTRUMENT — `call_type='download_batch'`** | THE batch chokepoint. ONE row per chunk with `ticker_count=len(chunk)` (NOT per-ticker) — keeps volume modest (§Volume). |
| 3 | `swing/patterns/labeling_bars.py:46` `_yf_download_window_for_labeling` | single-ticker daily window (`threads=False`) | CLI labeling auto-fetch ONLY (`autofetch_bars_for_labeling` ← `swing/cli.py:3792` `pattern label` emit path) | **INSTRUMENT — `call_type='download_single'`** | A genuine production yfinance call (operator labeling sessions). Deliberately NOT routed through `read_or_fetch_archive` (its docstring: arbitrary historical windows pre-date `archive_history_days`). Same DAILY-window shape as site 1 → reuses `download_single`. Surface = `'cli'`. |
| 4 | `swing/web/price_cache.py:206` `_fetch_live_price` | single-ticker INTRADAY minute bars (`period="1d", interval="1m", group_by="column", threads=False`) | web dashboard live-price fetch (`swing/web/app.py:293` `_yf_quote_fallback`) AND pipeline open-trade warm (`runner.py:398` `_quote_hook` ← `_warm_pipeline_marketdata`) | **INSTRUMENT — `call_type='download_intraday'`** | A DISTINCT shape from the daily chokepoints (minute interval). Treated as its own `call_type` so the monitors distinguish a slow/empty intraday quote from a slow/empty daily archive fetch (Codex R1: justified, not over-engineering). Called from BOTH web (`surface='web'`) and pipeline (`surface='pipeline'`); the process-global context disambiguates. |

**No site is silently skipped (#27).** Every `yf.download` invocation in `swing/` is instrumented, AND every entry point that can REACH a chokepoint sets an audit context (else the instrumentation no-ops → a #27 runtime skip). The reaching entry points are: the pipeline runner (`surface='pipeline'`); the web app (`surface='web'` base); and the CLI — NOT just `pattern label`, but ALSO **`swing eval` (`cli.py:384`) and `swing weather` (`cli.py:457`)**, which build a `PriceFetcher` → `read_or_fetch_archive` → `_yf_download_window` (Codex R4 MAJOR — these were missed in the first pass). A shared CLI helper sets a `surface='cli'` base context after config-load for EVERY CLI command that can reach `PriceFetcher`/`read_or_fetch_archive` (eval, weather, labeling, and any future archive-touching command). There is no test-only or dead `yf.download` in `swing/` to classify OUT. (Test fixtures monkeypatch `yf.download`; those are in `tests/`, out of scope — the instrumentation brackets the production call, and a monkeypatched `yf.download` under an active context still produces an audit row, which the discriminating tests exploit.) **Scope (Codex R5 NIT):** this audit covers production `swing/` yfinance surfaces ONLY; research-harness yfinance calls (e.g. `research/harness/earnings_proximity/fetchers.py`) are intentionally OUT of scope unless promoted into an app/runtime surface.

**Web coverage (Codex R1 MAJOR — resolved, no #27 contradiction):** the web dashboard live-price path (`app.py:293` → `_fetch_live_price`) and the web archive-read path (`app.py:320` → `read_or_fetch_archive` → `_yf_download_window`) ARE audited: the web app calls `set_yfinance_audit_base_context(surface='web', pipeline_run_id=None, db_path=app.state.cfg.paths.db_path)` once at startup AFTER `app.state.cfg` is finalized (post risk-policy divergence reconciliation — Codex R7 MINOR; the audit context is long-lived provenance, so don't bake in a pre-correction db_path) — the web server is a single long-lived process, so a once-set BASE tags every web-triggered yfinance call without needing per-request scoping. `surface='web'` is added to the `surface` CHECK enum (atomic in Task 0). (This is a deliberate choice over per-request scoping for V1 simplicity; a V2 could narrow to a request-scoped context mirroring `SWING_WEB_REQUEST_ID`.)

### Scope resolved before Task 0 (Codex R1 MINOR — no mid-task CHARC stop)

The enum set is FIXED before any code lands: `call_type IN ('download_single','download_batch','download_intraday')`; `surface IN ('pipeline','cli','web')`; `status IN ('in_flight','success','empty','error')`. The brief §2 named only `('download_single','download_batch')` and `surface IN ('pipeline','cli')` and anticipated "extend the enum if the §4 enumeration finds another distinct shape." The enumeration found the intraday shape (site 4) AND the web surface (site 4's web caller), so both extensions are folded in atomically at Task 0. **This is the brief-sanctioned extension path, surfaced to CHARC for the schema-design eye (return report), not a mid-execution stop.** Removed: the V1 `rate_limited` status (Codex R1 NIT — yfinance empties do not self-identify as rate-limited; there is no classifier to ever set it; `'empty'` stays first-class and carries the transient signal). If CHARC objects to the intraday/web extensions, the enum edit is a one-line CHECK + one frozenset entry — contained, but resolve BEFORE executing Task 0.

### Why a process-global audit context (not a threaded `conn`, not a `ContextVar`)

`swing/data/ohlcv_archive.py` is, by design, **DB-free** (pure file-IO + yfinance; imports nothing from `swing.data.db` or any repo). Its chokepoints are consumed by callers that do NOT all hold a DB connection or run context: `read_or_fetch_archive` (no `conn` param), `swing/web/app.py`, `swing/web/ohlcv_cache.py`, `swing/prices.py`, `swing/pipeline/ohlcv.py:fetch_daily_bars`, `swing/trades/daily_management.py`. Threading a `conn`/`run_id`/`surface` through every signature would be a large, invasive change that risks the "no measurement-chain change" lock.

The project already solved this exact problem in `swing/log_correlation.py` — a **lock-guarded module global** (NOT a `ContextVar`), with the documented rationale: *"the pipeline subprocess emits records from worker threads (the price-fetch executor, threaded steps) that would NOT inherit a `ContextVar` set on the main thread."* The same applies here: the audit context must tag yfinance calls made on PROCESS-WIDE consumers + worker threads (the price-fetch executor; threaded pipeline steps) where a `ContextVar` set on the main thread would silently drop (Codex R6 NIT — the `_fetch_chunk` `threads=True` is yfinance-INTERNAL, not a project worker pool; the global is justified by the process-wide + executor-thread consumers, not by `_fetch_chunk` specifically). The runner already calls `set_pipeline_run_id(lease.run_id)` at lease acquisition (`runner.py:592`).

**Design:** a new DB-free `swing/data/yfinance_audit_context.py` (mirroring `log_correlation.py`'s lock-guarded global) with TWO SEPARATE lock-guarded slots — a BASE slot and an ACTIVE-SCOPE slot (Codex R5/R8 MAJOR — explicit base/scope state, no surface-inference; and a base set must NOT clobber an active scope):
- A lock-guarded `_base: Ctx | None` (default `None`) AND a lock-guarded `_scope: Ctx | None` (default `None`), each `(db_path, pipeline_run_id, surface)`.
- `get_yfinance_audit_context()` → `_scope` if present, ELSE `_base`, ELSE `None`.
- `set_yfinance_audit_base_context(*, db_path, pipeline_run_id, surface)` — updates ONLY the `_base` slot; NEVER touches `_scope`. So a base set while a scope is active updates the base UNDER the scope (the scope still wins `get()`; the new base is what `get()` returns AFTER the scope exits). Replacing a base (app reconstruction) is allowed. Used by web startup (`surface='web'`) + the CLI base helper (`surface='cli'`).
- `@contextmanager yfinance_audit_scope(*, db_path, pipeline_run_id, surface)` — sets `_scope` on enter (capturing the prior `_scope` as a token); on EXIT restores it. **The production EXIT is NON-THROWING (Codex R11 MAJOR):** a LIFO-token mismatch is logged LOUDLY + best-effort-restored/cleared, but the `finally` NEVER raises out of the `with` block — audit-context cleanup must never mask a pipeline exception nor turn a successful run into a failed one. (A stricter test-only helper can assert mismatch detection; the production CM swallows.) Used by the pipeline runner (`surface='pipeline'`).
- **Single-active-scope guard (Codex R4 MAJOR):** `yfinance_audit_scope` REJECTS (raises `RuntimeError`) if `_scope` is already set (a second overlapping scope) — so a stray overlap fails LOUDLY rather than silently clobbering. A nested scope OVER a base is fine (the base is in `_base`, not `_scope`).
- `_set_for_test(...)` / `_reset_for_test()` — test seams; `_reset_for_test()` clears BOTH slots to `None` between tests.
- Tests: web base → pipeline scope → `set_base(cli)` while the scope is active → `get()` stays pipeline until the scope exits, THEN `get()` is the new `cli` base; a second overlapping scope raises; **the scope EXIT does NOT raise** (Codex R11 MAJOR — a scope whose exit detects a state mismatch does not raise out of the `with` block and does not alter the body's result/exception). (The internal LIFO token validation has no public driver — not separately asserted; Codex R9 NIT.)

**Concurrency — a HARD INVARIANT, bleed impossible by construction (Codex R3/R7 MAJOR):** the global is a single current-context slot. **The pipeline ALWAYS runs in a SEPARATE process from the web server** — this is an architectural FACT on disk, not a convention: the web POST `/pipeline/run` spawns the pipeline via `subprocess.Popen` (`swing/web/routes/pipeline.py:141`); the web server NEVER calls `run_pipeline` in-process. Therefore the web's `surface='web'` BASE context and the pipeline's `yfinance_audit_scope(surface='pipeline')` NEVER coexist in one process — the pipeline subprocess has NO web base (its scope sits over `None`), and the web process never enters a pipeline scope. There is **NO concurrent web-reader-during-pipeline-scope window**, so the "tag a concurrent web call as pipeline" bleed is **impossible by construction**, not a V1 limitation. The plan adds a test asserting the web app does NOT run `run_pipeline` in-process (it spawns a subprocess) so a future regression that introduces an in-process runner trips it. The `yfinance_audit_scope` LIFO token-restore + the single-active-non-base-scope guard are belt-and-suspenders (they make a stray same-process scope-over-scope raise, and a scope-over-`None`/base restore correctly). A V2 execution-local context is the only path IF an in-process web↔pipeline runner is ever added (which the invariant + test forbid). The web base is set once at app startup with no token (the outermost / process-lifetime context).

### The shared instrumentation helper `_record_yf_download` (lives in `swing/data/yfinance_audit.py`)

A single helper used at all 4 sites brackets the RAW `yf.download` (Codex R1 MAJOR — instrument around the raw call, never wrap whole functions). **DB-free-boundary discipline (Codex R2 MAJOR):** the helper lives in `swing/data/yfinance_audit.py` (which imports the repo + `swing.data.db.connect`). `ohlcv_archive.py` must NOT import it at module level (that would break `ohlcv_archive`'s deliberate DB-free-at-import property). Instead each chokepoint, when it sees an active context, does a **function-local (lazy) import** of `_record_yf_download` (a `from swing.data.yfinance_audit import _record_yf_download` inside the function body) — so `import swing.data.ohlcv_archive` pulls in NO repo/db module at import time. The no-context fast path imports nothing. (`labeling_bars.py` and `price_cache.py` already touch DB/CLI concerns, so a module-level import there is fine; only `ohlcv_archive.py` carries the DB-free-import constraint. A test asserts `import swing.data.ohlcv_archive` does not add `swing.data.db` / `swing.data.repos.yfinance_calls` to `sys.modules`.)

```
# The chokepoint snapshots the context ONCE and passes it in (no second
# get_yfinance_audit_context() inside the helper — Codex R3 MAJOR TOCTOU fix):
#   ctx = get_yfinance_audit_context()
#   if ctx is None: return yf.download(...)        # no import, no DB, zero new behavior
#   from swing.data.yfinance_audit import _record_yf_download   # lazy, DB-free import boundary
#   return _record_yf_download(ctx=ctx, call_type=..., ticker=..., ticker_count=...,
#                              fetch_fn=lambda: yf.download(...))

YFINANCE_AUDIT_BUSY_TIMEOUT_MS = 100   # Codex R3 CRITICAL: fail FAST on lock
                                       # contention so the audit never delays a fetch
                                       # (the project default is 30000ms -> would blow
                                       # the 3s web price-fetch deadline under contention)

# Serialization (Codex R11): a yfinance-specific _YF_AUDIT_WRITE_LOCK is held ONLY
# around each SHORT start/finish BEGIN IMMEDIATE tx (a sub-ms INSERT/UPDATE) -- NEVER
# around yf.download and never across a long wait. So same-process audits serialize
# deterministically (each sub-ms -> all rows record), there is NO N x fetch-time
# convoy (the lock is not held across the fetch), and the 100ms busy_timeout bounds
# CROSS-process contention (best-effort drop there only). record_call_start /
# record_call_finish own that lock + tx internally; the helper just calls them.
def _record_yf_download(*, ctx, call_type, ticker, ticker_count, fetch_fn):
    conn = None; call_id = None
    try:
        conn = connect(ctx.db_path, busy_timeout_ms=YFINANCE_AUDIT_BUSY_TIMEOUT_MS)
        call_id = record_call_start(conn, ts=now_iso(), call_type=call_type,
                                    ticker=ticker, ticker_count=ticker_count,
                                    pipeline_run_id=ctx.pipeline_run_id, surface=ctx.surface)
    except Exception:                # audit start failed/contended -> NEVER sink/delay the fetch
        log.warning(...); _safe_close(conn)
        return fetch_fn()            # fetch runs un-audited; measurement unaffected
    t0 = monotonic()                 # timer AROUND fetch_fn ONLY (Codex R10) -> yfinance
    try:                             #   latency, not audit-start overhead
        result = fetch_fn()
    except Exception as exc:         # the fetch raised
        _finish_safe(conn, call_id, status='error', rows=None, error=_sanitize(exc), t0=t0)
        _safe_close(conn)
        raise                        # PRESERVE the raise (single + intraday paths)
    # Post-fetch CLASSIFICATION is itself wrapped (Codex R8 CRITICAL): a hostile
    # .empty / __len__ on the result must NEVER replace a successful fetch.
    try:
        rows = _rows_of(result)      # len(df) | len(raw) | 0 for empty/None
        status = 'empty' if _is_empty(result) else 'success'
    except Exception:                # classification blew up -> do NOT sink the result
        log.warning(...); _finish_safe(conn, call_id, status='success', rows=None, error=None, t0=t0)
        _safe_close(conn)
        return result                # the EXACT original result, unchanged
    _finish_safe(conn, call_id, status=status, rows=rows, error=None, t0=t0)
    _safe_close(conn)
    return result
```

- **Low busy-timeout (Codex R3 CRITICAL):** the audit connection opens with `busy_timeout_ms=YFINANCE_AUDIT_BUSY_TIMEOUT_MS` (100ms) so a contended `BEGIN IMMEDIATE` fails FAST and the start-failure path runs `fetch_fn()` un-audited — the audit can NEVER block the fetch up to the 30s project default (which would blow the web price-fetch deadline). A test holds an external write transaction and asserts `_record_yf_download` calls `fetch_fn` + returns promptly (within a small bound) un-audited.
- **Serialization — short-critical-section lock (Codex R9/R10/R11, reconciled):** a yfinance-specific `_YF_AUDIT_WRITE_LOCK` is held ONLY around each SHORT start `BEGIN IMMEDIATE` tx and (separately) each short finish tx — a sub-ms INSERT/UPDATE — NEVER around `yf.download` and never across a long wait. So: (a) same-process concurrent audits serialize DETERMINISTICALLY (each critical section is sub-ms → all rows record, no flaky-CI drop — Codex R11 MINOR); (b) there is NO `N × fetch-time` convoy (R9) because the lock is not held across the deadline-sensitive fetch; (c) the `busy_timeout_ms=100` bounds CROSS-process contention only (best-effort drop there). Tests: N concurrent active-context fetches with NO external writer → all N rows recorded; N concurrent fetches WITH an external SQLite writer → all fetches return within deadline (some audits may best-effort drop).
- **Context snapshot (Codex R3 MAJOR TOCTOU):** `ctx` is captured ONCE at the chokepoint and passed in; the helper never re-reads `get_yfinance_audit_context()`. The SAME snapshot drives both start + finish — no window for the context to change between the chokepoint's null-check and the recorder's read.
- `_finish_safe` calls `record_call_finish` inside its own try/except — an audit-finish failure logs + is swallowed (never breaks the fetch / the caller's control flow). **The finish uses the SAME 100ms-busy-timeout connection** (Codex R8 MAJOR), so a contended finish fails fast (≤~100ms, bounded << the 3s web price-fetch deadline) — the audit FINISH (which runs after `yf.download` and before the caller returns) can never push a just-in-deadline quote into stale fallback. A finish-contention test (hold an external write lock AFTER `fetch_fn` returns) asserts the caller returns promptly with the original result.
- **Stale `in_flight` rows (Codex R10 MINOR):** a rare dropped finish (the 100ms-contention path) leaves the row `in_flight` permanently. So the row closes on every path EXCEPT a best-effort finish drop. The monitors (18-D/18-E) MUST treat a stale `in_flight` row (no terminal status, `ts` older than a small grace) as INCOMPLETE/unknown — NOT as a hung call — and the repo read helpers document this convention. NO new status is added (the enum lock holds).
- **Post-fetch classification is wrapped (Codex R8 CRITICAL):** `_rows_of(result)`/`_is_empty(result)` run in their own try/except; if classification raises (a hostile `.empty`/`__len__`, a yfinance shape change), the helper best-effort-finishes `success`/`rows=NULL` (or skips finish) and returns the EXACT original `fetch_fn()` result unchanged. The audit can never replace a successful fetch's result.
- **`success` semantics (Codex R11 MINOR):** `status='success'` means TRANSPORT/frame success (the raw `yf.download` returned rows) — NOT data USABILITY. An all-NaN-Close intraday frame records `success` (raw rows present) even though `_fetch_live_price` then raises its usability `RuntimeError` (the caller's concern). V1 keeps the raw-call-boundary classifier (no call-type-specific "no usable Close" → `empty`, which would re-introduce result-inspection into the audit path); a usability-aware classifier is a future candidate if a monitor needs it. Documented in the module docstring.
- The helper returns the EXACT `fetch_fn()` result; `fetch_fn` is a zero-arg closure capturing the unchanged `yf.download(...)` call + its kwargs.
- **Ticker normalization (Codex R4/R5/R7 MINOR):** the helper records the ticker upper-cased + trimmed in the audit row (metadata ONLY — the `yf.download(...)` argument inside `fetch_fn` is UNCHANGED) so monitor grouping does not split `aapl` vs `AAPL`. Inside the audit-start `try`: `t = str(ticker).strip().upper() if ticker is not None else None; ticker_meta = t or None` (an empty/whitespace ticker records `None`, not `""` — satisfies the `length(trim(ticker)) > 0` CHECK). If even metadata prep fails, `fetch_fn()` runs unchanged (metadata work must never become a new failure source).
- `_is_empty(result)`: for a DataFrame, `result is None or result.empty`. The helper is given a `is_empty`/`rows_of` policy per call_type (single/intraday return a df; batch returns the raw multi-index df). The CALLER's post-processing (squeeze, trim, extraction, the `_fetch_chunk` per-ticker loop, the `_fetch_live_price` empty→`RuntimeError`) happens AFTER the helper returns — so the audit sees the raw `yf.download` outcome, not a downstream-converted exception.

**Site-by-site bracketing (explicit — Codex R1 MAJOR on `_fetch_chunk` + `_fetch_live_price`).** Each site does: `ctx = get_yfinance_audit_context(); if ctx is None: <raw yf.download as today>; else: from swing.data.yfinance_audit import _record_yf_download; <route via _record_yf_download(ctx=ctx, ...)>` (the ctx-snapshot + lazy-import pattern):
- **`_yf_download_window` (single):** the function has NO try/except today; bracket the raw `yf.download(...)` via `_record_yf_download(ctx=ctx, call_type='download_single', ticker=ticker, ticker_count=None, fetch_fn=lambda: yf.download(...))`. The post-fetch squeeze/trim is OUTSIDE the bracket (unchanged). A raise propagates (audit closes `error` first).
- **`_fetch_chunk` (batch):** the EXISTING `try: raw = yf.download(...) except Exception: ...return ({}, list(chunk), True)` swallow is the tricky path. Do NOT wrap the whole function. Instead: call `_record_yf_download(ctx=ctx, call_type='download_batch', ticker=None, ticker_count=len(chunk), fetch_fn=lambda: yf.download(...))` and let the helper close `error` then re-raise; catch that re-raise in `_fetch_chunk`'s EXISTING `except Exception` and return the EXACT existing fallback `({}, list(chunk), True)`. Net: the audit row closes `error`, AND `_fetch_chunk`'s return contract is byte-identical. The `raw is None or raw.empty` branch → the helper records `empty` (it returns the empty frame; `_fetch_chunk` then returns its existing empty fallback). The success branch records `success` with `rows_returned=len(raw)`.
- **`_fetch_live_price` (intraday):** returns a `float`, and converts empty/all-NaN `yf.download` results into `RuntimeError` (`price_cache.py:219,231`). So bracket ONLY the raw `yf.download(...)` at `:206` (before the empty/NaN checks) via `_record_yf_download(ctx=ctx, call_type='download_intraday', ticker=ticker, ticker_count=None, fetch_fn=lambda: yf.download(...))`. The helper records `empty`/`success`/`error` from the RAW result; the existing `RuntimeError`-raising empty/NaN checks + the caller's fallback-to-last-close are UNCHANGED (they run on the helper's returned frame). This is the only correct way to record `status='empty'` + `rows_returned` for this site (Codex R1 MAJOR).
- **`_yf_download_window_for_labeling` (single):** same bracket as `_yf_download_window`.

### Disciplines preserved (CLAUDE.md §Gotchas)

- **#9** `executescript()` implicit COMMIT → migration 0030 uses explicit in-file `BEGIN; … COMMIT;` + in-file `UPDATE schema_version SET version = 30;`.
- **Backup-gate STRICT equality** (`pre_version == 29`, NOT `<=`) — `_cash_recon_backup_gate` is the verbatim template.
- **#11 atomic sweep** — `status` + `call_type` (+ `surface`) CHECK enums mirrored in Python constants + `YfinanceCall.__post_init__` frozensets + the read-path `_row_to_model` mapper, ALL in ONE task (Task 0). No committed intermediate state has a schema enum value unmirrored in Python or the read path (Codex R1 CRITICAL).
- **`INSERT OR REPLACE` cascade-wipe** — repo uses plain `UPDATE` for `update_call_outcome` (PK preserved); `test_update_call_outcome_preserves_pk` pins it.
- **`in_transaction` reject-caller-held** — the service owns `BEGIN IMMEDIATE` and rejects a caller-held tx (mirrors `audit_service.py`).
- **F6 empty-vs-error** — `'empty'` is FIRST-CLASS, distinct from `'error'`.
- **`... or None`** for nullable CHECK-constrained text (`error_message`).
- **ASCII discipline** — no non-ASCII in any user-facing/log string added.

---

## Locks (the merge gate QAs these on disk)

1. **NO measurement-chain change.** `validate_bars`, the archive parquet contents, the `_trim_trailing_ragged` trim, the candidate/temporal-log shapes, the `_fetch_live_price` float/RuntimeError contract, the `_fetch_chunk` `({}, list(chunk), True)` fallback: untouched. The audit records AROUND the raw `yf.download`; it never alters the call, its kwargs (`threads=False` single / authorized `threads=True` batch / the intraday `group_by="column"`), or its return value. An audit-write failure, lock-contention, OR a post-fetch classification exception is caught + logged, never propagated into (or allowed to DELAY) the fetch / replace its result — the audit connection uses a 100ms busy-timeout (start AND finish) so a contended `BEGIN IMMEDIATE` fails fast and the fetch runs un-audited (Codex R3/R8 CRITICAL/MAJOR), and the post-fetch `_rows_of`/`_is_empty` classification is wrapped so a hostile result object cannot replace a successful fetch (Codex R8 CRITICAL). **Proof on disk:** the helper returns the unmodified `yf.download` result; tests assert the returned DataFrame is identical with and without an active context, the `_fetch_chunk` fallback tuple is byte-identical when `yf.download` raises under an active context, the per-site `yf.download` kwargs are unchanged (kwargs-spy), and an externally-held write lock does not delay the fetch.
2. **#11 sweep atomic in one task** (Task 0): the `status` CHECK `('in_flight','success','empty','error')` + the `call_type` CHECK `('download_single','download_batch','download_intraday')` + the `surface` CHECK `('pipeline','cli','web')` mirrored in `_YFINANCE_VALID_STATUSES` + `_YFINANCE_VALID_CALL_TYPES` + `_YFINANCE_VALID_SURFACES` (Python frozensets/tuple) + `YfinanceCall.__post_init__` (frozenset checks — `Literal` NOT runtime-enforced) + the repo `_row_to_model` read-path mapper + the repo `insert_in_flight`/`update_call_outcome` shape, all landed in the SAME commit. `grep swing/` for hardcoded copies before closing the task.
3. **Always-on recording (NO sandbox gate; best-effort under cross-process contention).** **Crisp definition (Codex R7 NIT):** "always-on" = the audit is always ATTEMPTED when a context is active, NEVER sandbox-gated; it is BEST-EFFORT on SQLite/audit failures (fast-fail, never blocks/sinks the fetch — it does NOT guarantee every active-context call records a row). Unlike `_step_schwab_*`, the yfinance audit attempts in ALL environments — NO `environment` column, NO production-only short-circuit. Recording fires whenever a context is active, regardless of `cfg.integrations.schwab.environment`. **It is "always-on, BEST-EFFORT" (Codex R4 MAJOR):** the in-process `_AUDIT_WRITE_LOCK` serializes only WITHIN a process; the web/pipeline/CLI are separate processes contending only through SQLite, where the 100ms fast-fail busy-timeout can occasionally DROP an audit row under cross-process write contention — a DELIBERATE trade (the fetch deadline + the no-measurement-change lock dominate audit completeness; 18-D/18-E consume rates/trends that tolerate rare drops). **Proof on disk:** the helper has no `environment` read; a test under `environment='sandbox'` still records a row.
4. **Light redaction.** yfinance carries NO auth token → NO `setLogRecordFactory` (deliberate — documented in `yfinance_audit.py` docstring). `error_message` is defensively sanitized: collapse whitespace + truncate to 200 chars (matching the runner `[:200]` precedent at `runner.py:1308`). A yfinance exception may embed a URL with query params (benign — no secret); truncation is hygiene.
5. **Discriminating tests** (§Testing): empty → `status='empty'` (NOT error); exception → `status='error'` + row closed before re-raise; success → timing + `rows_returned`; row closes on every path EXCEPT a rare best-effort finish-contention drop (which leaves `in_flight` — monitors treat as incomplete); both-ways regression arithmetic; batch = ONE row with `ticker_count`; the audit-failure-does-not-break-fetch isolation; the always-on (no-environment) behavior; the `_fetch_chunk` fallback byte-parity under a raising `yf.download`.

---

## Schema — `yfinance_calls` (migration `0030`, v29 → v30)

`swing/data/migrations/0030_phase18_yfinance_call_audit.sql`:

```sql
-- 0030_phase18_yfinance_call_audit.sql
-- Lands the yfinance_calls audit table (Phase 18 Arc 18-C) mirroring
-- schwab_api_calls (0018) for yfinance fetch observability (feeds 18-D/18-E).
-- Atomic via explicit BEGIN; ... COMMIT; per CLAUDE.md gotcha #9
-- "executescript() implicit COMMIT" (runner-level rollback can only undo
-- partial DDL when the SQL itself opens an explicit transaction).
-- Bumps schema_version 29 -> 30.
--
-- TWO deliberate divergences from schwab_api_calls (BY DESIGN):
--   (1) status CHECK includes 'empty' as a FIRST-CLASS value, DISTINCT from
--       'error' (CLAUDE.md F6 gotcha): yfinance returns empty for rate-limit /
--       network / weekend reasons, a transient data-collection signal the
--       monitors must distinguish from a hard error.
--   (2) NO `environment` column. yfinance is the always-on, environment-
--       agnostic fetcher (no sandbox/production domain-row gating, unlike
--       Schwab). Adding it would imply a gating that does not exist.

BEGIN;

CREATE TABLE yfinance_calls (
    call_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT NOT NULL,             -- ISO 8601 naive; call start
    call_type         TEXT NOT NULL,
    ticker            TEXT,                      -- single/intraday shapes
    ticker_count      INTEGER,                   -- batch shape (N tickers, ONE row)
    response_time_ms  INTEGER,
    status            TEXT NOT NULL,
    rows_returned     INTEGER,                   -- rows in the frame yf.download returned; 0 on empty
    error_message     TEXT,                      -- sanitized/truncated yfinance exc string
    pipeline_run_id   INTEGER,                   -- FK to pipeline_runs(id); NULL for cli/web
    surface           TEXT NOT NULL,

    CHECK (call_type IN (
        'download_single', 'download_batch', 'download_intraday'
    )),
    CHECK (status IN (
        'in_flight', 'success', 'empty', 'error'
    )),
    CHECK (surface IN ('pipeline', 'cli', 'web')),

    -- Numeric defense-in-depth under the dataclass (Codex R3 MINOR — inserts
    -- bypass dataclass validation):
    CHECK (response_time_ms IS NULL OR response_time_ms >= 0),
    CHECK (rows_returned   IS NULL OR rows_returned   >= 0),
    CHECK (ticker_count    IS NULL OR ticker_count    >  0),
    -- No empty/whitespace ticker for single/intraday rows (Codex R7 MINOR):
    CHECK (ticker IS NULL OR length(trim(ticker)) > 0),

    -- Shape invariant (Codex R3 MINOR): batch carries ticker_count (ticker NULL);
    -- single/intraday carry ticker (ticker_count NULL). Holds at insert time too
    -- (the in-flight row is inserted WITH the shape fields populated — both are
    -- known at call start).
    CHECK (
        (call_type = 'download_batch'
            AND ticker_count IS NOT NULL AND ticker IS NULL)
        OR
        (call_type IN ('download_single', 'download_intraday')
            AND ticker IS NOT NULL AND ticker_count IS NULL)
    ),

    FOREIGN KEY (pipeline_run_id)
        REFERENCES pipeline_runs(id)
        ON DELETE SET NULL
);

CREATE INDEX ix_yfinance_calls_ts
    ON yfinance_calls(ts);

CREATE INDEX ix_yfinance_calls_status_ts
    ON yfinance_calls(status, ts);

CREATE INDEX ix_yfinance_calls_pipeline_run_id_ts
    ON yfinance_calls(pipeline_run_id, ts);

CREATE INDEX ix_yfinance_calls_call_type_ts
    ON yfinance_calls(call_type, ts);

CREATE INDEX ix_yfinance_calls_surface_ts
    ON yfinance_calls(surface, ts);          -- monitors filter by surface (mirrors schwab)

CREATE INDEX ix_yfinance_calls_ticker_ts
    ON yfinance_calls(ticker, ts);           -- ticker-level health is a natural yfinance query

UPDATE schema_version SET version = 30;

COMMIT;
```

Notes:
- `pipeline_runs` PK is `id` (migration 0003), so the FK references `pipeline_runs(id)` (same column `schwab_api_calls` references).
- `ticker` vs `ticker_count`: single/intraday set `ticker` (leave `ticker_count` NULL); batch sets `ticker_count=len(chunk)` (leave `ticker` NULL). **The SQL shape CHECK intentionally enforces this** (Codex R3/R4) — both shape fields are known at call start, so the in-flight INSERT already satisfies it; the dataclass `__post_init__` is the defense-in-depth mirror.
- `rows_returned`: ONE definition everywhere (Codex R1 MAJOR) — the row count of the frame `yf.download` returned: single = `len(df)`, batch = `len(raw)` (the multi-index frame), intraday = `len(df)`; `0` on empty/None. `ticker_count` carries batch width; `rows_returned` is the upstream yfinance response size. The plan does NOT compute a per-ticker sum.
- Dropped from `schwab_api_calls`: `http_status`, `rate_limit_remaining`, `signature_hash`, `linked_*` (yfinance has no HTTP-status surface, no rate-limit header we read, no snapshot/reconciliation linkage). Per brief §6, a monitor needing a column 18-C didn't provide = an additive migration THEN.

### Migration runner — backup gate (`swing/data/db.py`)

Add `_create_pre_phase18_arc_c_migration_backup` (filename prefix `swing-pre-phase18-arc-c-migration-`) + `_phase18_arc_c_backup_gate` mirroring `_cash_recon_backup_gate` verbatim:
- Fires ONLY when `current_version == 29 AND target_version >= 30` (STRICT equality, NOT `<=`).
- Expected-tables constant `PHASE18_ARC_C_PRE_MIGRATION_EXPECTED_TABLES = CASH_RECON_PRE_MIGRATION_EXPECTED_TABLES`. **Provenance (corrected, Codex R1 MINOR):** the pre-v30 (v29) table set EQUALS the pre-v29 (cash-recon) table set because 0029 adds NO new table (it rebuilds `cash_movements` + ALTERs `account_equity_snapshots`). The cash-recon alias chain ALREADY includes the `pipeline_step_timings` table added by 0025; 0030 is the first NEW table since then. Do NOT claim "0025–0029 added no tables" (false — 0025 added `pipeline_step_timings`).
- Register the gate call in `run_migrations` after `_cash_recon_backup_gate`.
- Bump `EXPECTED_SCHEMA_VERSION = 29` → `30`.

---

## Tasks (TDD: red → green → commit per task)

### Task 0 — THE atomic enum-bearing landing: migration 0030 + `YfinanceCall` model + `yfinance_calls` repo (the #11 sweep in ONE commit)

> Codex R1 CRITICAL: the SQL CHECK + Python constants + dataclass frozensets + the repo `_row_to_model` mapper MUST land in ONE task/commit so no committed intermediate state has a schema enum value unmirrored in Python + the read path. The service + instrumentation (Tasks 1–4) consume these but do not redefine them.

- [ ] **Migration tests** (`tests/data/test_migration_0030_yfinance_calls.py`): table/11-columns/6-indexes/CHECKs (enum + numeric + shape) via `PRAGMA table_info` + `sqlite_master`; INSERT `status='empty'` ok, `status='bogus'` → `IntegrityError`; `call_type='download_intraday'` ok, `'frobnicate'` rejected; `surface='web'` ok, `'mobile'` rejected; the numeric CHECKs (negative `response_time_ms`/`rows_returned`, `ticker_count<=0` rejected) + the shape CHECK (a `download_batch` row with `ticker` set, or a `download_single` row with `ticker_count` set, rejected); a valid `download_batch` in-flight row (`ticker_count` set, `ticker` NULL) accepted; the empty-ticker CHECK (`ticker=''` / whitespace rejected — Codex R7 MINOR); **FK behavior under `PRAGMA foreign_keys=ON`** (Codex R7 MINOR): insert-with-valid-`pipeline_run_id` ok; an invalid `pipeline_run_id` rejected; deleting the `pipeline_runs` row NULLs the audit row's `pipeline_run_id` (`ON DELETE SET NULL`) — catches a wrong FK column / missing action; **migrate-twice no-op** (run `run_migrations` twice; version stays 30, no error); backup-gate STRICT-equality (v29 file DB → creates `swing-pre-phase18-arc-c-migration-*.db`; fresh v0 walk does NOT fire this gate); `EXPECTED_SCHEMA_VERSION == 30`.
- [ ] **Model tests** (`tests/data/test_yfinance_call_model.py`): valid `YfinanceCall` constructs; `status`/`call_type`/`surface` outside the frozensets → `ValueError`; `response_time_ms` negative / bool → `ValueError`; `rows_returned` negative → `ValueError`; `error_message=None` ok; **shape-invariant mirror (Codex R6 MINOR)** — `download_batch` with `ticker` set / without `ticker_count`, and `download_single`/`download_intraday` with `ticker_count` set / without `ticker`, each → `ValueError` (the dataclass `__post_init__` mirrors the SQL shape CHECK); an empty/whitespace `ticker` → `ValueError` (mirrors the `length(trim(ticker)) > 0` CHECK — Codex R7 MINOR).
- [ ] **Repo tests** (`tests/data/repos/test_yfinance_calls_repo.py`): `insert_in_flight` returns `call_id`, row `status='in_flight'`; `update_call_outcome` sets terminal fields + **PRESERVES PK** (`test_update_call_outcome_preserves_pk`); `get_call` round-trips through `_row_to_model`; `_row_to_model` maps all columns in order (a column-order regression test).
- [ ] Implement, in ONE commit: the migration SQL; the backup-gate fn + expected-tables constant + `run_migrations` registration + `EXPECTED_SCHEMA_VERSION` bump; the `_YFINANCE_VALID_STATUSES`/`_YFINANCE_VALID_CALL_TYPES`/`_YFINANCE_VALID_SURFACES` constants + `@dataclass YfinanceCall` (`__post_init__` validators: enum frozensets, bool-is-int reject for int fields, non-negative numeric, AND the batch-vs-single SHAPE invariant mirroring the SQL shape CHECK) in `swing/data/models.py`; the `swing/data/repos/yfinance_calls.py` repo (`_SELECT_COLUMNS`, `_row_to_model`, `insert_in_flight(conn, *, ts, call_type, ticker, ticker_count, pipeline_run_id, surface)` [status hardcoded `'in_flight'`; caller controls tx — NO `commit()`], `update_call_outcome(conn, *, call_id, response_time_ms, status, rows_returned, error_message)` [plain `UPDATE`, never `INSERT OR REPLACE`], `get_call`). **Enum-grep rule (Codex R5 NIT — precise):** the SCHEMA CHECK + the Python VALIDATOR copies (the `_YFINANCE_VALID_*` constants + the dataclass `__post_init__` frozensets + the read-path `_row_to_model`) must mirror atomically and be the ONLY validator/check sets — grep `swing/` to confirm NO additional validator/check set drifts. Call sites passing enum LITERALS/constants (`call_type='download_single'`, `surface='web'`, etc.) are fine and expected; the grep is not against call-site literals. See fail → see pass.
- [ ] Commit: `feat(data): Task 0 — yfinance_calls schema 0030 + model + repo (atomic #11 enum sweep, v29->v30)`.

### Task 1 — the audit context global with push/pop semantics (`swing/data/yfinance_audit_context.py`)

> Reordered BEFORE the service (Codex R2 MAJOR — the service's `_record_yf_download` tests consume the context's `_set_for_test`, so the context must exist first).

- [ ] Tests (`tests/data/test_yfinance_audit_context.py`): `set_yfinance_audit_base_context(...)` → get round-trips; a base can be REPLACED (app reconstruction); `yfinance_audit_scope(...)` CM sets on enter + restores the prior context (base or None) on exit; **nested over base** (set a `web` base; inside a `yfinance_audit_scope(surface='pipeline', run_id=7)`, get → pipeline; after the scope, get → the `web` base, NOT None); **base-set does NOT clobber an active scope** (Codex R8 MAJOR — web base → pipeline scope → `set_base(cli)`; `get()` stays pipeline until the scope exits, THEN `get()` is the new `cli` base); **single-active-scope guard** (Codex R4/R6/R8 — a second overlapping scope while one is active RAISES `RuntimeError`; the scope token-restore + LIFO validation are INTERNAL details of the CM, not a public `reset(token)` API, so they are not asserted via a public seam — Codex R9 NIT); default (unset) → `None`; `_set_for_test`/`_reset_for_test` seams.
- [ ] Implement the lock-guarded TWO-SLOT global (DB-free; mirroring `log_correlation.py`) — a `_base` slot + a `_scope` slot — with `set_yfinance_audit_base_context(...)` (updates `_base` only; never touches `_scope`), `@contextmanager yfinance_audit_scope(...)` (sets/clears `_scope`; LIFO token-restore + single-active-scope guard), `get_yfinance_audit_context` (`_scope` else `_base` else `None`), `_set_for_test`/`_reset_for_test` (clears both). See fail → see pass.
- [ ] Commit: `feat(data): Task 1 — yfinance audit context (lock-guarded global, push/pop token-restore)`.

### Task 2 — `yfinance_audit` service + the `_record_yf_download` helper (`swing/data/yfinance_audit.py`)

- [ ] Tests (`tests/data/test_yfinance_audit_service.py`): `record_call_start` inserts in-flight + returns id; `record_call_finish` sets terminal fields; both REJECT a caller-held tx (`CallerHeldTransactionError`); concurrent N-writer serialization via the short-critical-section `_YF_AUDIT_WRITE_LOCK` + per-call `BEGIN IMMEDIATE` records all N rows; the stale-`in_flight`-excluding repo read helper; `_sanitize_error` collapses whitespace + truncates to 200; **`_record_yf_download` unit tests** (passing an explicit `ctx` snapshot — no internal `get_yfinance_audit_context`) with a fake `fetch_fn` + a real on-disk DB: success (rows+timing+`success`), empty-df (`empty`, rows 0), raising `fetch_fn` (`error` + row closed + re-raises), **audit-START-failure isolation** (a bogus `db_path` → `fetch_fn()` still returns; no raise), **audit-FINISH-failure isolation** (force `record_call_finish`/`_finish_safe` to raise on the success, empty, AND error paths → the original return/re-raise unchanged) (Codex R2 MINOR), **lock-contention-does-not-delay** (hold an external write tx; `_record_yf_download` still calls `fetch_fn` + returns within a small bound, un-audited — the 100ms audit busy-timeout) (Codex R3 CRITICAL); **finish-contention-does-not-delay** (hold an external write lock AFTER `fetch_fn` returns; the caller returns promptly with the original result — finish fails fast ≤100ms) (Codex R8 MAJOR); and **post-fetch-classification-failure isolation** (`fetch_fn` returns an object whose `.empty`/`__len__` RAISES → `_record_yf_download` returns the EXACT object unchanged + best-effort records a `success`/`rows=NULL` row, never sinks the call) (Codex R8 CRITICAL).
- [ ] Implement mirroring `audit_service.py` (the `record_call_start`/`record_call_finish` halves, `in_transaction` reject, `BEGIN IMMEDIATE`/COMMIT/ROLLBACK) with a yfinance-specific `_YF_AUDIT_WRITE_LOCK` held ONLY around each short start/finish tx (a sub-ms INSERT/UPDATE — never across `yf.download`; Codex R11 — deterministic same-process serialization, no fetch-time convoy) + the audit connection opened with `busy_timeout_ms=100` + the `_record_yf_download` helper (§The shared instrumentation helper) + `_sanitize_error` + `_safe_close`/`_finish_safe` (BOTH the start and finish audit calls wrapped so neither can sink/delay the fetch) + repo read helpers that EXCLUDE/classify stale `in_flight` rows (terminal-status filter — Codex R11). Module docstring documents the deliberate light-redaction posture (no auth token → no `setLogRecordFactory`) + the short-critical-section-lock + low-busy-timeout deadline-protection + the success-semantics (transport/frame success, not usability). NO `environment` param anywhere. NO sandbox gate.
- [ ] Commit: `feat(data): Task 2 — yfinance_audit service + _record_yf_download helper (reject caller-held tx; always-on; start+finish failure isolation; light redaction)`.

### Task 3 — instrument the two `ohlcv_archive.py` chokepoints (single + batch) — DB-free-import preserved

- [ ] Tests (`tests/data/test_ohlcv_archive_yfinance_audit.py` — the discriminators, §Testing): monkeypatch `yf.download` with a **kwargs-asserting spy** (Codex R2 MINOR — single asserts `threads=False`, the exact start/end/progress/auto_adjust/actions; batch asserts `threads=True`, `group_by='ticker'`); under an active context assert single-success/empty/raise, batch one-row/raise/empty (per §Testing); under NO context no row + identical return + **`import swing.data.ohlcv_archive` adds NO `swing.data.db`/`swing.data.repos.yfinance_calls` to `sys.modules`** (the DB-free-import test, Codex R2 MAJOR); always-on under `environment='sandbox'`; audit-failure-does-not-break-fetch.
- [ ] Bracket the raw `yf.download` at `_yf_download_window:257` and `_fetch_chunk:503`: when `get_yfinance_audit_context()` is not `None`, do a function-local `from swing.data.yfinance_audit import _record_yf_download` and route the raw call through it (§Site-by-site bracketing); else call `yf.download` directly (no import). The `_fetch_chunk` `except Exception` keeps its existing fallback return; the helper's `error`-then-re-raise is caught there. See fail → see pass. grep: no enum drift.
- [ ] Commit: `feat(data): Task 3 — instrument ohlcv_archive single+batch chokepoints (lazy recorder import; DB-free at module import)`.

### Task 4 — instrument labeling + price_cache; set the context at runner / CLI / web

- [ ] Tests:
  - `tests/patterns/test_labeling_bars_yfinance_audit.py`: under a `surface='cli'` context, `autofetch_bars_for_labeling` records a `download_single` row (kwargs-spy `threads=False`); empty → `empty`; without context → no row + identical behavior.
  - **CLI eval/weather coverage** (Codex R4 MAJOR): tests that `swing eval` (`cli.py:384`) and `swing weather` (`cli.py:457`) run under a `surface='cli'` base context so their `PriceFetcher`→`_yf_download_window` calls record `download_single` rows (monkeypatched `yf.download`) — NOT a #27 runtime skip.
  - extend price_cache tests: under a `surface='web'`/`'pipeline'` scope, `_fetch_live_price` records a `download_intraday` row (kwargs-spy asserts `period="1d"`, `interval="1m"`, `group_by="column"`, `timeout=<cfg>`, `threads=False`); empty `yf.download` → `status='empty'` + the existing `RuntimeError("no bars")` STILL raises (proves bracketing the raw call, not the method); all-NaN → `success` row (raw had rows) + the existing all-NaN `RuntimeError` STILL raises (the audit sees the raw frame, the NaN check is downstream).
  - `tests/pipeline/test_runner_yfinance_audit_context.py`: a run enters a `yfinance_audit_scope(surface='pipeline', run_id=<real>, db_path=...)` and RESTORES the prior context on exit (assert prior restored, not unconditionally cleared). **Early-return coverage (Codex R3 MAJOR):** assert the prior context is ALSO restored when the run aborts early (a finviz inbox/select failure path and an evaluation-failure path that `return RunResult(state="failed")` before the body completes) — the scope must wrap EVERY post-`set_pipeline_run_id` return.
  - a web-app test: app construction sets the persistent `surface='web'` base context FROM the finalized `app.state.cfg` (assert via `get_yfinance_audit_context`); a simulated nested pipeline scope inside an app process restores the `web` base on exit.
  - **the hard-invariant tests (Codex R7/R9 MAJOR):** (a) the web POST `/pipeline/run` spawns the pipeline as a SUBPROCESS (`subprocess.Popen` at `web/routes/pipeline.py:141`); (b) a BROADER static/AST guard scanning ALL of `swing/web/` rejects an in-process import/call of `run_pipeline` (the subprocess command construction in `pipeline.py` is the only allowed reference) — so a future in-process web runner ANYWHERE under `swing/web/` (re-opening the web↔pipeline bleed window) trips it.
  - **context-installation assertions per entry point (Codex R9 MINOR):** for `swing eval`/`weather`/`pattern label`, web startup, and the pipeline run, assert `get_yfinance_audit_context()` is POPULATED at the actual chokepoint WITHOUT pre-seeding the global in the test (catches an entry point that forgets to install context).
- [ ] Bracket `_yf_download_window_for_labeling:46` + `_fetch_live_price`'s raw `yf.download:206` via the ctx-snapshot + `_record_yf_download` pattern (these two modules already touch DB/CLI concerns, so a module-level import of the recorder is fine here). Set the context: **runner** — enter ONE OUTER `with yfinance_audit_scope(surface='pipeline', pipeline_run_id=lease.run_id, db_path=cfg.paths.db_path):` IMMEDIATELY after `set_pipeline_run_id(lease.run_id)` (`runner.py:592`), STRUCTURALLY enclosing the heartbeat create/start + the ENTIRE post-lease body through the existing `finally` — so EVERY post-lease `return RunResult(...)` is lexically inside the scope (restoration guaranteed) AND no post-lease yfinance call runs before the scope opens (Codex R3/R9 MAJOR). **No-raise production entry (Codex R10 MAJOR):** the scope entry must NOT strand a lease — wrap the entry so a scope-guard/entry failure (a stale/overlapping scope) is caught + logged + degrades to no-audit (the lease + run proceed normally); an audit-context problem must NEVER wedge a pipeline lease. An AST/structural test asserts every post-lease `return RunResult` is inside the `with` block (not just the finviz/evaluate examples); a test pre-seeds an active scope, runs the runner path, and asserts the run proceeds + the lease releases normally (NOT left wedged); **CLI** — a shared helper `install_yfinance_cli_audit_context(cfg)` sets a `surface='cli'` BASE context AFTER final `cfg` resolution (incl. any overrides — Codex R6 MINOR) in EVERY archive-reaching command (`eval` `cli.py:384`, `weather` `cli.py:457`, `pattern label`, and any future one — Codex R4 MAJOR, eval/weather were the gap); test harnesses reset the global between Click invocations; **web app startup** (`set_yfinance_audit_base_context(surface='web', pipeline_run_id=None, db_path=app.state.cfg.paths.db_path)` once, AFTER `app.state.cfg` is finalized — Codex R7 MINOR — the persistent outermost base, no token restore needed). The CLI base helper uses `set_yfinance_audit_base_context(surface='cli', pipeline_run_id=None, ...)`. See fail → see pass. grep: no enum drift.
- [ ] Commit: `feat(data): Task 4 — instrument labeling+price_cache; set audit context at runner/CLI/web (scope-restore at runner/CLI; web base at startup)`.

### Task 5 — full-suite green + ruff + final #11 sweep

- [ ] `python -m pytest -m "not slow" -q` from the worktree — record the tail count for the return report.
- [ ] `ruff check swing/` clean.
- [ ] Final grep for hardcoded enum copies across `swing/`.

---

## Testing — the discriminating tests (LOCK 5)

All in `tests/` (style-matched to siblings; ≤100-char lines, local imports). Chokepoint tests monkeypatch `yf.download` (never the network) with a **kwargs-asserting spy** + set a test context via `yfinance_audit_scope` / `_set_for_test`.

| test | asserts | distinguishes (pre-fix vs post-fix arithmetic) |
|------|---------|------------------------------------------------|
| `test_each_site_preserves_exact_yf_download_kwargs` | a spy `yf.download` asserts the EXACT positional+keyword args per site (single `threads=False`; batch `threads=True`+`group_by='ticker'`; intraday `period/interval/group_by/timeout/threads=False`; labeling `threads=False`) | an impl that drops/changes a kwarg (e.g. `threads`, `group_by`, `timeout`) → spy assertion fails (the no-measurement-change lock) (Codex R2 MINOR) |
| `test_single_success_records_timing_and_rows` | `download_single` row, `status='success'`, `rows_returned == len(df)`, `response_time_ms >= 0`, `ticker` set / `ticker_count` NULL | a no-op records 0 rows → fails; the bracket records exactly 1 |
| `test_single_empty_records_empty_not_error` | empty `yf.download` → `status='empty'`, `rows_returned == 0`, NOT `'error'` | a "non-success = error" impl records `'error'` → fails `== 'empty'`; the F6-correct impl passes |
| `test_single_exception_records_error_and_closes_row_before_reraise` | `yf.download` raises → call re-raises AND a closed `status='error'` row with `error_message` exists | an impl closing only on success leaves `in_flight` after the raise → fails; close-on-every-path passes |
| `test_batch_one_row_with_ticker_count` | N-ticker chunk → ONE row, `download_batch`, `ticker_count==N`, `ticker` NULL, `rows_returned==len(raw)` | a per-ticker impl records N rows → fails "exactly 1" |
| `test_batch_chunk_exception_records_error_and_fetch_falls_back_byte_identical` | `_fetch_chunk`'s `yf.download` raises → row `status='error'` closed AND the fn returns `({}, list(chunk), True)` | proves the audit close fires in the swallow path AND the fetch contract is unchanged (the no-measurement-change lock) |
| `test_intraday_empty_records_empty_and_caller_still_raises_runtimeerror` | `_fetch_live_price` empty `yf.download` → `status='empty'` row AND the existing `RuntimeError("no bars")` STILL raises | proves bracketing the RAW call, not the method (a method-wrap would record `error` + can't see empty) |
| `test_intraday_allnan_records_success_and_caller_still_raises` | all-NaN closes → `status='success'` (raw had rows) AND the all-NaN `RuntimeError` STILL raises | proves the audit sees the raw frame; the NaN check is downstream + unchanged |
| `test_no_context_no_row_identical_return` | NO context: no row AND the returned frame is identical to a direct `yf.download` | proves opt-in recording — the no-measurement-change lock |
| `test_audit_start_failure_does_not_break_fetch` | force `record_call_start` to raise (bogus `db_path`) → the fetch STILL returns its normal result | an impl letting the audit exception propagate sinks the fetch → fails; the isolated try/except passes |
| `test_audit_finish_failure_does_not_break_fetch` (success/empty/error paths) | force `record_call_finish`/`_finish_safe` to raise on each terminal path → the original return / re-raise is unchanged | an impl isolating only START but not FINISH → fails (Codex R2 MINOR) |
| `test_success_result_returned_when_audit_rows_of_or_is_empty_raises` | `fetch_fn` returns an object whose `.empty`/`__len__` RAISES → `_record_yf_download` returns the EXACT object unchanged | an impl that classifies OUTSIDE a try replaces the result with the classifier's exception → fails (Codex R8 CRITICAL — the no-measurement-change lock) |
| `test_audit_finish_contention_does_not_delay_fetch` | hold an external write lock AFTER `fetch_fn` returns → the caller returns promptly (≤~100ms finish) with the original result | a default-busy-timeout finish blocks the caller past the price-fetch deadline → fails (Codex R8 MAJOR) |
| `test_base_set_does_not_clobber_active_scope` | web base → pipeline scope → `set_base(cli)`; `get()` stays pipeline until the scope exits, then is the new `cli` base | a single-slot base setter overwrites the active scope → fails (Codex R8 MAJOR) |
| `test_ohlcv_archive_import_is_db_free` | in a FRESH SUBPROCESS (`python -c "import sys, swing.data.ohlcv_archive; assert 'swing.data.db' not in sys.modules and 'swing.data.repos.yfinance_calls' not in sys.modules"`), the import does NOT pull in `swing.data.db` / the repo | a module-level recorder import breaks the DB-free-at-import property → the subprocess assert fails (Codex R2 MAJOR; subprocess isolation per Codex R4 NIT so it can't false-pass on an already-imported module) |
| `test_audit_lock_contention_does_not_delay_fetch` | hold an external write tx; `_record_yf_download` STILL calls `fetch_fn` + returns promptly (bounded; 100ms SQLite + non-blocking Python lock), un-audited | a default-30s-busy-timeout impl blocks the fetch up to 30s → fails the prompt-return bound (Codex R3 CRITICAL) |
| `test_concurrent_fetches_no_writer_record_all_rows` | N concurrent active-context fetches with NO external SQLite writer → all N audit rows recorded within deadline (the short-critical-section lock serializes deterministically) | a non-blocking-lock impl drops audits among concurrent web misses even with SQLite free → fails (Codex R10/R11 MAJOR — always-on best-effort in the common path) |
| `test_concurrent_fetches_with_writer_return_within_deadline` | N concurrent fetches WITH an external SQLite writer → ALL fetches return within the deadline (some audits may best-effort drop) | a blocking-lock impl convoys N×100ms past the deadline → fails (Codex R9 CRITICAL) |
| `test_runner_scope_entry_failure_does_not_strand_lease` (Task 4) | pre-seed an active scope; run the runner path → the run proceeds + the lease releases normally (no-raise scope entry) | a raising scope-entry after lease acquisition wedges the lease → fails (Codex R10 MAJOR) |
| `test_migration_0030_numeric_and_shape_checks` | INSERT negative `response_time_ms`/`rows_returned`, `ticker_count<=0`, a `download_batch` row with `ticker` set, a `download_single` row with `ticker_count` set → each raises `IntegrityError` | a missing numeric/shape CHECK accepts the malformed row → fails (Codex R3 MINOR) |
| `test_always_on_records_under_sandbox` (unit) | `environment='sandbox'` + active context → a row IS recorded | a copied `_step_schwab_*` short-circuit inside `_record_yf_download` records 0 → fails (LOCK 3) |
| `test_entrypoint_records_under_sandbox_without_presetting_context` (Codex R5 MAJOR) | run the runner/CLI adapter under `environment='sandbox'` WITHOUT manually pre-setting context → yfinance rows ARE recorded | a wrong impl that simply does not SET the context under sandbox passes the unit test but fails THIS one |
| `test_no_context_call_imports_nothing` (Codex R5 MINOR) | in a FRESH SUBPROCESS, a no-context chokepoint call (monkeypatched `yf.download`) completes AND `swing.data.db`/the repo are NOT in `sys.modules` afterward | an impl that lazy-imports the recorder BEFORE checking context → fails (the no-context fast path must import nothing) |
| `test_update_call_outcome_preserves_pk` (repo) | insert→id; update→same id; re-read by id→updated fields | a stray `INSERT OR REPLACE` reassigns the PK → fails |
| `test_migration_0030_*` (Task 0) | table/columns/indexes/CHECKs; migrate-twice no-op; backup-gate strict equality; `EXPECTED_SCHEMA_VERSION==30` | — |
| `test_context_scope_restores_prior` (Task 1) | a `web` base; inside a `yfinance_audit_scope(surface='pipeline')` get→pipeline; after the scope get→the `web` base (NOT None) | proves push/pop restore — a pipeline scope does NOT disable web recording (Codex R2 MAJOR) |
| `test_runner_scope_restores_prior_context` (Task 4) | a run enters a `pipeline` scope and RESTORES the prior context on exit | proves scope-restore, not an unconditional clear (no web-base clobber, no stale bleed) |
| `test_every_post_lease_return_is_inside_the_scope` (Task 4, AST) | static/AST scan: every `return RunResult(...)` after `set_pipeline_run_id` is lexically inside the outer `with yfinance_audit_scope(...)` | an impl wrapping only the happy path leaves a failure return outside the scope → fails (Codex R9 MAJOR) |
| `test_web_has_no_in_process_run_pipeline` (Task 4, static) | AST/grep under `swing/web/`: no in-process import/call of `run_pipeline` (only the `pipeline.py` subprocess command construction) | a future in-process web runner re-opens the bleed window → fails (Codex R9 MINOR) |
| `test_labeling_records_download_single` / `test_web_app_sets_web_base_context` (Task 4) | full enumeration coverage (#27 no silent skip) | — |

---

## Risks / deviations / V1 simplifications

- **Intraday `'download_intraday'` + `surface='web'` enum extensions** — surfaced to CHARC for the schema-design eye (return report). Justified (distinct fetch shape; real web call path). The enum is FIXED before Task 0 (no mid-task stop). If CHARC drops them: a one-line CHECK + one frozenset entry each (contained), and Task 4's price_cache/web wiring drops with them. **Resolve before executing Task 0.**
- **Web base uses `app.state.cfg.paths.db_path` (Codex R8 MINOR)** — installed after `app.state.cfg` is finalized. Only `db_path` matters for the audit base, and the risk-policy divergence reconciliation supersedes `risk_policy` rows, NOT `paths.db_path` — so the finalized-cfg install equals the raw-cfg `db_path` (belt-and-suspenders). Aligning `PriceCache`/`OhlcvCache` construction to `app.state.cfg` is a separate concern OUT of this arc's scope (they already use the raw cfg; no `db_path` change risk).
- **Web context is the persistent (process-lifetime) BASE, not per-request** — the web server is long-lived with no clean per-request run boundary; a once-set `set_yfinance_audit_base_context(surface='web', ...)` tags every web-triggered yfinance call. This audits the web paths (resolving the Codex R1 #27 contradiction) at the cost of no per-request run-id (`pipeline_run_id=NULL` for web rows — correct, web has no pipeline run). A nested in-process pipeline run uses `yfinance_audit_scope` (LIFO token-restore) so it restores the web base on exit and never clobbers it (Codex R2/R5 MAJOR). V2: a request-scoped context mirroring `SWING_WEB_REQUEST_ID`.
- **`rows_returned` = `len(<frame yf.download returned>)`** everywhere (single/intraday `len(df)`; batch `len(raw)`); `ticker_count` carries batch width. NOT a per-ticker sum (Codex R1 MAJOR — single definition).
- **Per-chokepoint short-lived `connect(db_path, busy_timeout_ms=100)`** — the chokepoints can't share the pipeline's `audit_conn` (no threaded conn). Volume is ~10–15 calls/night (§Volume), so the per-call `connect()` is negligible. The `_AUDIT_WRITE_LOCK` serializes audit writes WITHIN a process; ACROSS processes (web/pipeline/CLI) the 100ms fast-fail busy-timeout means a cross-process write-lock collision drops the audit row rather than blocking the fetch — recording is best-effort under cross-process contention (Codex R4 MAJOR), NOT a strong cross-connection serialization guarantee.
- **Concurrency-safety** (Codex R3/R4/R7 MAJOR): the single-slot global is data-race-free (lock-guarded); the `yfinance_audit_scope` single-active-non-base-scope guard makes a stray same-process overlap raise rather than silently clobber. The web⇄pipeline bleed is impossible BY CONSTRUCTION: the pipeline always runs in a subprocess (`web/routes/pipeline.py:141` `subprocess.Popen`; the web never runs `run_pipeline` in-process — a test pins this), so the `surface='web'` base and the `surface='pipeline'` scope never share a process. No V1 limitation here.

## Volume + retention (per brief — noted, NOT this arc)

A batch call = ONE row (not per-ticker), so nightly volume ≈ warm chunk count + warm-miss single fallbacks + open-trade intraday warms ≈ 10–15 rows/night, the same order as `schwab_api_calls`. Per-call granularity is affordable. A long-term prune (mirroring `swing logs cleanup` / the exports archiver) is future hygiene, NOT 18-C.

## R1 (`requests` dep) — does NOT ride this arc (brief §6 + §10)

18-C adds NO dependency (yfinance + sqlite already declared) and does NOT touch `pyproject.toml`. R1 (the `requests` declaration) needs its own tiny dispatch or a later pyproject-touching host. Do not fold it in.
