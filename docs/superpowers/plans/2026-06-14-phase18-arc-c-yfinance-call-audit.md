# Phase 18 Arc 18-C — yfinance call audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Read `CLAUDE.md` (gotchas) + `docs/phase18-arc-c-dispatch-brief.md` first; re-ground every file:line anchor against live code (line numbers drift).

**Goal:** Add a `yfinance_calls` audit table (migration `0030`, schema v29 → v30) + a recording service mirroring `schwab_api_calls` / `swing/integrations/schwab/audit_service.py`, so that yfinance fetches become observable (timings, errors, empties, rows, run-linkage) to feed 18-D (RD research monitor) + 18-E (tool-health monitor). **Purely additive observability** — it records AROUND the existing `yf.download` calls and changes nothing about what they fetch, their kwargs, their result, or how the measurement consumes them.

**Architecture (settled — NO brainstorm).** Mirror the Schwab three-piece transactional discipline: a `swing/data/repos/yfinance_calls.py` repo (caller-controlled tx; `insert_in_flight` → `update_call_outcome`; UPDATE-in-place, never `INSERT OR REPLACE`), a `swing/data/yfinance_audit.py` service (`record_call_start` / `record_call_finish`; owns `BEGIN IMMEDIATE`; rejects caller-held tx; `_AUDIT_WRITE_LOCK`-serialized), a `YfinanceCall` dataclass in `swing/data/models.py` with `__post_init__` frozenset validators, and the two chokepoint wrappers in `swing/data/ohlcv_archive.py` (`_yf_download_window` single; `_fetch_chunk` batch). The chokepoints do NOT take a `conn` (their many consumers don't thread one) — instead they read a **lock-guarded process-global audit context** (`db_path` + `pipeline_run_id` + `surface`), set by the entry points that DO have it (the pipeline runner; the CLI), exactly mirroring the established `swing/log_correlation.py` process-global pattern (chosen there, and here, BECAUSE the warm runs `threads=True` and a `ContextVar` would silently drop on worker threads). Absent context (unit tests, web-only paths) = recording no-ops.

**Tech Stack:** Python 3.14, sqlite3, pytest. **NO new dependency** (yfinance + sqlite already declared; R1 `requests` does NOT ride this arc — see §10). **NO `pyproject` touch.** New schema/migration (the §3-tripwire crossing this brief authorizes). Touches `swing/data/` (the authorized carve-out for this arc: new table + repo + model + service + the two chokepoint wrappers in `ohlcv_archive.py` + a new `swing/data/yfinance_audit_context.py`), `swing/pipeline/runner.py` + `swing/cli.py` (set the context), `swing/data/db.py` (backup gate). NO `swing/trades/` touch.

---

## Background — re-grounding (verified on disk at branch start, base `ad8138b6`)

### The `yf.download` enumeration (FIRST DELIVERABLE — audit-to-confirm, #27)

`grep -rn "yf\.download(" swing/` returns exactly **5 invocation sites** in **4 files** (every `yf.download` is an actual call; no commented call sites in `swing/`):

| # | site (file:line) | shape | runtime path | disposition | reason |
|---|------------------|-------|--------------|-------------|--------|
| 1 | `swing/data/ohlcv_archive.py:257` `_yf_download_window` | single-ticker daily window (`threads=False`) | pipeline warm-miss serial loops + CLI + web archive reads | **WRAP — `call_type='download_single'`** | THE single chokepoint; reached by `read_or_fetch_archive` (the gap + full-refresh branches) which fans out to the runner, `swing/web/app.py`, `swing/web/ohlcv_cache.py`, `swing/prices.py`, `swing/pipeline/ohlcv.py`. Recording lives AT the chokepoint, not the callers, so all consumers get audited with one wrap. |
| 2 | `swing/data/ohlcv_archive.py:503` `_fetch_chunk` | multi-ticker batch (`threads=True`, `group_by='ticker'`) | pipeline `_step_evaluate` warm (`warm_archives_batch` → `_warm_one_window` → `_fetch_chunk`) | **WRAP — `call_type='download_batch'`** | THE batch chokepoint. ONE row per chunk with `ticker_count=len(chunk)` (NOT per-ticker) — keeps volume modest (§Volume). |
| 3 | `swing/patterns/labeling_bars.py:46` `_yf_download_window_for_labeling` | single-ticker daily window (`threads=False`) | CLI labeling auto-fetch ONLY (`autofetch_bars_for_labeling` ← `swing/cli.py:3792` `pattern label` emit path) | **WRAP — `call_type='download_single'`** | A genuine production yfinance call (operator labeling sessions). Deliberately NOT routed through `read_or_fetch_archive` (its module docstring explains: arbitrary historical windows pre-date `archive_history_days`). It is a distinct DAILY-window fetch, same shape as site 1, so it reuses `download_single`. Surface = `'cli'`. |
| 4 | `swing/web/price_cache.py:206` `_fetch_live_price` | single-ticker INTRADAY minute bars (`period="1d", interval="1m", group_by="column", threads=False`) | web dashboard live-price fetch (market-hours only) AND pipeline open-trade warm (`runner.py:398` `_quote_hook` ← `_warm_pipeline_marketdata`) | **WRAP — `call_type='download_intraday'` (NEW enum value)** | This is a DISTINCT shape from the daily-window chokepoints (minute interval, not the inclusive daily window). The §4 enumeration finding a distinct shape = the brief §2 "extend the enum if the enumeration finds another distinct shape" path → a #11 sweep that adds `'download_intraday'` to the `call_type` CHECK + the Python mirror + the dataclass frozenset, all in the same task. Called from BOTH web (surface `'cli'` per the schwab "web == cli surface" precedent) and pipeline (surface `'pipeline'`) — the process-global context disambiguates. |
| (5) | — | — | — | (sites 1–4 are the complete set; this row is intentionally blank to make the "5 invocations, 4 files" count explicit) | — |

**No site is silently skipped (#27).** Every `yf.download` invocation routes through the audit wrapper. There is no test-only or dead `yf.download` in `swing/` to classify OUT. (Test fixtures monkeypatch `yf.download`; those are in `tests/`, out of scope — the audit wraps the production call site, and a monkeypatched `yf.download` under a set context still produces an audit row, which the discriminating tests exploit.)

> **Enumeration finding flagged to CHARC (surfaced in the return report, not absorbed):** the brief §2 named `call_type IN ('download_single', 'download_batch')` and anticipated "extend the enum if the §4 enumeration finds another distinct shape." The enumeration DID find a third distinct shape: the `price_cache._fetch_live_price` **intraday minute-bar** fetch (site 4). This is NOT a daily window — folding it into `download_single` would conflate two genuinely different fetch shapes the monitors must distinguish (a slow/empty intraday quote ≠ a slow/empty daily archive fetch). The plan therefore adds a THIRD `call_type` value `'download_intraday'`, landed atomically in the #11 sweep (Task 4). This is exactly the brief-sanctioned extension path, not a scope change; it is called out here for CHARC's schema-design eye. **If CHARC prefers site 4 stay OUT of scope** (audit only the two ohlcv_archive chokepoints + labeling), the plan drops Task 6 (the price_cache wrap) and the `'download_intraday'` enum value, with no other change. Resolve before executing.

### Why a process-global audit context (not a threaded `conn`, not a `ContextVar`)

`swing/data/ohlcv_archive.py` is, by design, **DB-free** (pure file-IO + yfinance; imports nothing from `swing.data.db` or any repo). Its chokepoints are consumed by callers that do NOT all hold a DB connection or run context: `read_or_fetch_archive` (no `conn` param), `swing/web/app.py`, `swing/web/ohlcv_cache.py`, `swing/prices.py`, `swing/pipeline/ohlcv.py:fetch_daily_bars`, `swing/trades/daily_management.py`. Threading a `conn`/`run_id`/`surface` through every one of those signatures would be a large, invasive surface change that risks the "no measurement-chain change" lock.

The project already solved this exact "thread run context to a deep helper that runs on worker threads" problem in `swing/log_correlation.py` — a **lock-guarded module global** (NOT a `ContextVar`), with the documented rationale (file header): *"the pipeline subprocess emits records from worker threads (the price-fetch executor, threaded steps) that would NOT inherit a `ContextVar` set on the main thread."* The warm's `_fetch_chunk` runs under `threads=True`, so a `ContextVar` would be the wrong tool here too. The runner already calls `set_pipeline_run_id(lease.run_id)` at lease acquisition (`runner.py:592`).

**Design:** a new `swing/data/yfinance_audit_context.py` (DB-free, mirroring `log_correlation.py`'s shape):
- A lock-guarded global holding an immutable context: `(db_path: Path, pipeline_run_id: int | None, surface: str)`, plus an "active" flag (default: inactive → recording no-ops).
- `set_yfinance_audit_context(*, db_path, pipeline_run_id, surface)` — set + activate. Called by the pipeline runner (right after `set_pipeline_run_id`, `surface='pipeline'`, `db_path=cfg.paths.db_path`) and by the CLI labeling path (`surface='cli'`, `pipeline_run_id=None`). Resolve `pipeline_run_id` from the existing `log_correlation.get_pipeline_run_id()` is NOT used (it returns a placeholder string `"-"`); the runner passes the real `lease.run_id` int directly.
- `clear_yfinance_audit_context()` — deactivate (called in the runner's `finally`, mirroring how the audit_conn is closed in `finally`).
- `get_yfinance_audit_context()` → the context or `None` when inactive.
- `_set_for_test(...)` / `_reset_for_test()` — test seams (mirroring `log_correlation._set_for_test`).

The chokepoint wrapper: read `get_yfinance_audit_context()`; if `None` → just call `yf.download` exactly as today (zero new behavior). If present → open a short-lived `connect(ctx.db_path)`, `record_call_start` (in-flight row), run the EXACT existing `yf.download`, then `record_call_finish` on EVERY path (success / empty / error), closing the row before re-raising, then close the connection. **The audit code is wrapped in its OWN try/except so an audit failure NEVER breaks the fetch** (a DB-locked audit write must not sink a pipeline fetch — log a warning and proceed; mirrors the warm's best-effort posture). This is the load-bearing "no measurement-chain change" guarantee.

### Disciplines preserved (CLAUDE.md §Gotchas)

- **#9** `executescript()` implicit COMMIT → migration 0030 uses explicit in-file `BEGIN; … COMMIT;` + in-file `UPDATE schema_version SET version = 30;`.
- **Backup-gate STRICT equality** (`pre_version == 29`, NOT `<=`) — the Phase-9 clause shape (`_cash_recon_backup_gate` is the verbatim template).
- **#11 atomic sweep** — `status` + `call_type` CHECK enums mirrored in Python constants + `YfinanceCall.__post_init__` frozensets + the read-path `_row_to_model` mapper, ALL in one task (Task 4).
- **`INSERT OR REPLACE` cascade-wipe** — the repo uses plain `UPDATE` for `update_call_outcome` (PK preserved); a `test_update_call_outcome_preserves_pk` pins it.
- **`in_transaction` reject-caller-held** — the service owns `BEGIN IMMEDIATE` and rejects a caller-held tx (mirrors `audit_service.py`).
- **F6 empty-vs-error** — `'empty'` is a FIRST-CLASS status distinct from `'error'` (an empty `yf.download` result records `status='empty'`, never `'error'`).
- **`... or None`** for nullable CHECK-constrained text (`error_message`).
- **ASCII discipline** — no non-ASCII in any user-facing/log string added.

---

## Locks (the merge gate QAs these on disk)

1. **NO measurement-chain change.** `validate_bars`, the archive parquet contents, the `_trim_trailing_ragged` trim, the candidate/temporal-log shapes: untouched. The audit records AROUND `yf.download`; it never alters the call, its kwargs (`threads=False` single / authorized `threads=True` batch / the intraday `group_by="column"`), or its return value. An audit-write failure is caught + logged, never propagated into the fetch. **Proof on disk:** the wrapper returns the unmodified `yf.download` result; a test asserts the returned DataFrame is byte-identical with and without an active context.
2. **#11 sweep atomic in one task** (Task 4): the `status` CHECK `('in_flight','success','empty','error','rate_limited')` + the `call_type` CHECK `('download_single','download_batch','download_intraday')` mirrored in `_YFINANCE_VALID_STATUSES` + `_YFINANCE_VALID_CALL_TYPES` (Python frozensets) + `YfinanceCall.__post_init__` (frozenset checks — `Literal` is NOT runtime-enforced) + the repo `_row_to_model` read-path mapper + any repo INSERT guard, all landed together. `grep swing/` for hardcoded copies of either tuple before closing the task.
3. **Always-on recording (NO sandbox gate).** Unlike `_step_schwab_*`, the yfinance audit records in ALL environments — there is NO `environment` column and NO production-only short-circuit. The recording fires whenever a context is active, regardless of `cfg.integrations.schwab.environment`. **Proof on disk:** the wrapper has no `environment` read; a test under `environment='sandbox'` still records a row.
4. **Light redaction.** yfinance carries NO auth token, so NO `setLogRecordFactory` machinery (deliberate — documented in `yfinance_audit.py` module docstring). `error_message` is defensively sanitized: collapse whitespace + truncate to a fixed cap (200 chars, matching the runner's `[:200]` precedent at `runner.py:1308`). A yfinance exception may embed a URL with query params (benign — no secret), so truncation is hygiene, not security.
5. **Discriminating tests** (§Testing): empty → `status='empty'` (NOT error); exception → `status='error'` + row closed before re-raise; success → timing + `rows_returned`; row closes on EVERY path; both-ways regression arithmetic where it applies; batch = ONE row with `ticker_count`; the audit-failure-does-not-break-fetch isolation; the always-on (no-environment) behavior.

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
    rows_returned     INTEGER,                   -- total rows across the call; 0 on empty
    error_message     TEXT,                      -- sanitized/truncated yfinance exc string
    pipeline_run_id   INTEGER,                   -- FK to pipeline_runs(id); NULL for CLI
    surface           TEXT NOT NULL,

    CHECK (call_type IN (
        'download_single', 'download_batch', 'download_intraday'
    )),
    CHECK (status IN (
        'in_flight', 'success', 'empty', 'error', 'rate_limited'
    )),
    CHECK (surface IN ('pipeline', 'cli')),

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

UPDATE schema_version SET version = 30;

COMMIT;
```

Notes:
- `pipeline_runs` PK is `id` (set by migration 0003), so the FK references `pipeline_runs(id)` (the same column `schwab_api_calls` references; 0018's comment banks the plan-text-vs-actual `run_id`/`id` drift — we use `id`, the real column).
- `ticker` vs `ticker_count`: per brief, a single/intraday call sets `ticker` (and leaves `ticker_count` NULL); a batch call sets `ticker_count=len(chunk)` (and leaves `ticker` NULL). No CHECK couples them (the dataclass `__post_init__` is the soft contract; over-constraining the SQL is unnecessary and risks brittle migrations).
- `rows_returned`: total rows across the call (single = `len(df)`; batch = sum of rows across all returned tickers, computed from the raw frame the chokepoint already builds; 0 on empty).
- The `signature_hash` / `http_status` / `rate_limit_remaining` / `linked_*` columns from `schwab_api_calls` are intentionally DROPPED — yfinance has no HTTP-status surface, no rate-limit header we read, and no snapshot/reconciliation linkage. (Per brief §6: a monitor needing a column 18-C didn't provide = an additive migration THEN.)

### Migration runner — backup gate (`swing/data/db.py`)

Add `_create_pre_phase18_arc_c_migration_backup` (filename prefix `swing-pre-phase18-arc-c-migration-`) + `_phase18_arc_c_backup_gate` mirroring `_cash_recon_backup_gate` verbatim:
- Fires ONLY when `current_version == 29 AND target_version >= 30` (STRICT equality, NOT `<=`).
- Expected-tables constant `PHASE18_ARC_C_PRE_MIGRATION_EXPECTED_TABLES = CASH_RECON_PRE_MIGRATION_EXPECTED_TABLES` (0030 is the FIRST table-add since 0024, so the pre-v30 / v29 table set equals the cash-recon pre-migration set — 0025–0029 added no tables; document this provenance in the comment, mirroring the existing alias chain).
- Register the gate call in `run_migrations` after `_cash_recon_backup_gate`.
- Bump `EXPECTED_SCHEMA_VERSION = 29` → `30`.

---

## Tasks (TDD: red → green → commit per task)

### Task 0 — `yfinance_calls` migration 0030 + backup gate + version bump

- [ ] Write `tests/data/test_migration_0030_yfinance_calls.py`:
  - migrate a fresh DB to v30; assert `yfinance_calls` exists with the 11 columns + 4 indexes + the 3 CHECK constraints (introspect `sqlite_master` / `PRAGMA table_info`).
  - **migrate-twice no-op** test: run `run_migrations` twice; assert version stays 30, no error, table unchanged (the #9 idempotency pin).
  - INSERT a row with `status='empty'` succeeds; INSERT `status='bogus'` raises `IntegrityError` (CHECK fires); same for `call_type` (`'download_intraday'` accepted; `'frobnicate'` rejected) + `surface`.
  - backup-gate STRICT-equality test: a v29 file-backed DB migrating to v30 creates `swing-pre-phase18-arc-c-migration-*.db`; a fresh (v0) DB walking to v30 does NOT fire this gate (mirrors the cash-recon gate's strict-equality test).
  - `EXPECTED_SCHEMA_VERSION == 30` assertion.
- [ ] Add the migration SQL, the backup-gate function + expected-tables constant + the `run_migrations` registration, bump `EXPECTED_SCHEMA_VERSION`. See fail → see pass.
- [ ] Commit: `feat(data): Task 0 — yfinance_calls migration 0030 (v29->v30) + backup gate`.

### Task 1 — `YfinanceCall` dataclass + validators (`swing/data/models.py`)

- [ ] Write `tests/data/test_yfinance_call_model.py`: a valid `YfinanceCall` constructs; `status` / `call_type` / `surface` outside the frozensets raise `ValueError`; `response_time_ms` negative / non-int(bool) raises; `rows_returned` negative raises; `error_message=None` ok.
- [ ] Add `_YFINANCE_VALID_STATUSES = frozenset({'in_flight','success','empty','error','rate_limited'})`, `_YFINANCE_VALID_CALL_TYPES = frozenset({'download_single','download_batch','download_intraday'})`, `_YFINANCE_VALID_SURFACES = ('pipeline','cli')` + the `@dataclass class YfinanceCall` (fields mirroring the columns; `call_id: int | None`) with `__post_init__` validators. Mirror the `SchwabApiCall` validator style (bool-is-int reject for the int fields).
- [ ] Commit: `feat(data): Task 1 — YfinanceCall dataclass + frozenset validators`.

### Task 2 — `yfinance_calls` repo (`swing/data/repos/yfinance_calls.py`)

- [ ] Write `tests/data/repos/test_yfinance_calls_repo.py`: `insert_in_flight` returns a `call_id`, row has `status='in_flight'`; `update_call_outcome` sets terminal fields **and PRESERVES the PK** (`test_update_call_outcome_preserves_pk` — insert, capture id, update, re-read by that id, assert same id + updated fields); `get_call` round-trips through `_row_to_model`; `_row_to_model` maps all columns in order.
- [ ] Implement the repo mirroring `schwab_api_calls.py`: `_SELECT_COLUMNS`, `_row_to_model`, `insert_in_flight(conn, *, ts, call_type, ticker, ticker_count, pipeline_run_id, surface)` (status hardcoded `'in_flight'`; caller controls tx — NO `commit()`), `update_call_outcome(conn, *, call_id, response_time_ms, status, rows_returned, error_message)` (plain `UPDATE`, never `INSERT OR REPLACE`). Optional read helpers (`list_recent_calls`, `count_calls_by_status`) only if trivially mirrored — keep V1 lean (the monitors are 18-D/18-E; they add their own reads if needed).
- [ ] Commit: `feat(data): Task 2 — yfinance_calls repo (UPDATE-in-place, PK preserved)`.

### Task 3 — `yfinance_audit` service (`swing/data/yfinance_audit.py`)

- [ ] Write `tests/data/test_yfinance_audit_service.py`: `record_call_start` inserts an in-flight row + returns the id; `record_call_finish` sets terminal fields; both REJECT a caller-held tx (`CallerHeldTransactionError`); `_AUDIT_WRITE_LOCK`-serialized (smoke); `error_message` sanitizer collapses whitespace + truncates to 200 chars.
- [ ] Implement mirroring `audit_service.py` (the `record_call_start` / `record_call_finish` halves, the `_AUDIT_WRITE_LOCK`, the `in_transaction` reject, `BEGIN IMMEDIATE`/COMMIT/ROLLBACK). Module docstring documents the **light-redaction posture is deliberate** (no auth token → no `setLogRecordFactory`; only the `_sanitize_error` whitespace-collapse + truncate). NO `environment` param anywhere.
- [ ] Commit: `feat(data): Task 3 — yfinance_audit service (BEGIN IMMEDIATE; reject caller-held tx; light redaction)`.

### Task 4 — audit context + the single + batch chokepoint wraps (THE #11-sensitive integration)

> This task lands the #11 sweep already (the enums are defined in Tasks 0/1/2; this task only WIRES them). It also lands the audit-context global + both `ohlcv_archive.py` chokepoint wraps. Keep it ONE commit so the wire-up + the context land atomically.

- [ ] Write `tests/data/test_yfinance_audit_context.py`: set → get round-trips; clear → get is `None`; default (unset) → `None`.
- [ ] Implement `swing/data/yfinance_audit_context.py` (lock-guarded global mirroring `log_correlation.py`: `set_yfinance_audit_context`, `clear_yfinance_audit_context`, `get_yfinance_audit_context`, `_set_for_test`, `_reset_for_test`).
- [ ] Write `tests/data/test_ohlcv_archive_yfinance_audit.py` (the discriminators — see §Testing): monkeypatch `yf.download` to return a non-empty frame / an empty frame / raise; under an active context assert a row with the right `status` / `rows_returned` / `response_time_ms` / `call_type` / closed-on-every-path; under NO context assert no row + identical return; the audit-failure-isolation test; the always-on (sandbox) test.
- [ ] Wrap `_yf_download_window` (single) + `_fetch_chunk` (batch) in a shared internal helper `_record_yf_download(call_type, ticker, ticker_count, fetch_fn)` that: reads `get_yfinance_audit_context()`; if `None` → `return fetch_fn()`; else open `connect(ctx.db_path)`, `record_call_start`, run `fetch_fn()` capturing rows/empty/exception, `record_call_finish` (close on EVERY path, before re-raise), close conn — ALL audit code in a try/except that logs + proceeds on audit failure so the fetch is never sunk. The `yf.download` call + its kwargs are UNCHANGED inside `fetch_fn`.
  - Single: `rows_returned = len(df)`; empty (`df is None or df.empty`) → `status='empty'`, `rows=0`.
  - Batch: `ticker_count = len(chunk)`; `rows_returned = len(raw)` (the raw multi-index frame the chokepoint already builds); whole-chunk empty/None → `status='empty'`; the `except Exception` (already present at `_fetch_chunk:508`) → `status='error'` + row closed, then the EXISTING fallback return (`{}, list(chunk), True`) is preserved (the audit close happens, the fetch behavior is byte-identical).
  - **Crucial:** the existing `_fetch_chunk` already SWALLOWS its exception (serial fallback). The audit must close the row as `'error'` in that swallow path — the row closes even though the exception does NOT re-raise. (The single path's `_yf_download_window` does NOT have a try/except today; if `yf.download` raises there it propagates to the caller — the audit closes as `'error'` BEFORE re-raising, preserving the raise.)
- [ ] grep `swing/` for any hardcoded copy of either enum tuple; confirm only the model constants + the migration CHECK + the dataclass frozensets hold them. See fail → see pass.
- [ ] Commit: `feat(data): Task 4 — yfinance audit context + ohlcv_archive single+batch chokepoint wraps (#11 sweep wired)`.

### Task 5 — set the context at the pipeline runner

- [ ] Write `tests/pipeline/test_runner_yfinance_audit_context.py`: a pipeline run sets `surface='pipeline'` + the real `pipeline_run_id` + `db_path` on the context (assert via `get_yfinance_audit_context`), and CLEARS it in the `finally` (assert `None` after the run). Use the existing runner test harness/fixtures.
- [ ] In `run_pipeline_internal`, right after `set_pipeline_run_id(lease.run_id)` (`runner.py:592`), call `set_yfinance_audit_context(db_path=cfg.paths.db_path, pipeline_run_id=lease.run_id, surface='pipeline')`; in the run's `finally` (where `audit_conn` is closed), call `clear_yfinance_audit_context()`. See fail → see pass.
- [ ] Commit: `feat(pipeline): Task 5 — set yfinance audit context under the pipeline lease`.

### Task 6 — labeling + price_cache chokepoint wraps + the CLI context (the intraday enum is already in the schema from Task 0)

> **GATED on the CHARC ruling for site 4** (see the §enumeration flag). If CHARC keeps site 4 OUT, this task wraps ONLY `labeling_bars` (single) and drops the price_cache wrap + the `'download_intraday'` enum value (a one-line CHECK edit + frozenset edit, done in Task 0/1's enums — so removing it is contained). Default plan = wrap both.

- [ ] Write `tests/patterns/test_labeling_bars_yfinance_audit.py` + extend the price_cache tests: under an active `surface='cli'` context, `autofetch_bars_for_labeling` records a `download_single` row; `_fetch_live_price` records a `download_intraday` row (empty → `status='empty'`; raise → `status='error'` + closed). Without context → no row + identical behavior.
- [ ] Wrap `_yf_download_window_for_labeling` (single) + `_fetch_live_price` (intraday) using the SAME `_record_yf_download` helper (lift it to a shared location both modules import — `swing/data/yfinance_audit.py` is the natural home, since it's the DB-aware seam; `ohlcv_archive.py` imports it from there to keep `ohlcv_archive` DB-free of the repo but it WILL import the audit helper — acceptable, the helper is the recording seam). `price_cache._fetch_live_price` already imports `connect`; the helper centralizes the conn handling.
- [ ] Set the CLI labeling context: in `swing/cli.py` at the `pattern label` emit path (around `:3792` where `autofetch_bars_for_labeling` is called), wrap with `set_yfinance_audit_context(db_path=cfg.paths.db_path, pipeline_run_id=None, surface='cli')` / `clear_yfinance_audit_context()` in a `finally`. (The web price-fetch path does NOT set a context in V1 — web requests don't have a clean run boundary; an unset context = no-op, which is correct. The pipeline open-trade warm path (`_quote_hook`) inherits the `surface='pipeline'` context already set by Task 5, so its `_fetch_live_price` calls ARE recorded. Document this V1 scoping: web-dashboard live-price fetches are intentionally NOT audited in V1 — no run boundary; a V2 web-request-scoped context could add them.)
- [ ] grep confirm no enum drift; see fail → see pass.
- [ ] Commit: `feat(data): Task 6 — labeling + price_cache chokepoint wraps + CLI labeling audit context`.

### Task 7 — full-suite green + ruff + #11 final sweep

- [ ] `python -m pytest -m "not slow" -q` from the worktree (cwd discovery tests the worktree code) — record the tail count for the return report.
- [ ] `ruff check swing/` clean.
- [ ] Final grep sweep for hardcoded enum copies across `swing/`.
- [ ] (No commit unless a fix is needed; if a fix lands, conventional commit.)

---

## Testing — the discriminating tests (LOCK 5)

All in `tests/` (style-matched to siblings; ≤100-char lines, local imports). The chokepoint tests monkeypatch `yf.download` (never hit the network) + set a test context via `_set_for_test`.

| test | asserts | distinguishes (pre-fix vs post-fix arithmetic) |
|------|---------|------------------------------------------------|
| `test_single_success_records_timing_and_rows` | `download_single` row, `status='success'`, `rows_returned == len(df)`, `response_time_ms >= 0`, `ticker` set / `ticker_count` NULL | a no-op wrapper records NO row (count 0) → fails; the wrap records exactly 1 → passes |
| `test_single_empty_records_empty_not_error` | empty `yf.download` (returns `pd.DataFrame()`) → `status='empty'`, `rows_returned == 0`, NOT `'error'` | a naive "non-success = error" impl records `'error'` → fails the `== 'empty'` assert; the F6-correct impl passes |
| `test_single_exception_records_error_and_closes_row_before_reraise` | `yf.download` raises → the call re-raises (single path has no swallow) AND a closed `status='error'` row exists with `error_message` set | an impl that closes the row only on success leaves `status='in_flight'` after the raise → fails; close-on-every-path passes |
| `test_batch_one_row_with_ticker_count` | a chunk of N tickers → exactly ONE row, `call_type='download_batch'`, `ticker_count == N`, `ticker` NULL, `rows_returned == len(raw)` | a per-ticker impl records N rows → fails the "exactly 1" assert |
| `test_batch_chunk_exception_records_error_but_fetch_still_falls_back` | `_fetch_chunk`'s `yf.download` raises → row `status='error'` closed AND the function STILL returns `({}, list(chunk), True)` (byte-identical fallback) | proves the audit close fires in the swallow path AND the fetch contract is unchanged |
| `test_no_context_no_row_identical_return` | with NO active context: no `yfinance_calls` row written AND the returned frame is identical to a direct `yf.download` | proves recording is opt-in (web paths / unit tests unaffected) — the "no measurement-chain change" lock |
| `test_audit_failure_does_not_break_fetch` | force `record_call_start` to raise (e.g. point `db_path` at an unwritable/bogus path) → the fetch STILL returns its normal result (audit failure logged, swallowed) | an impl that lets the audit exception propagate sinks the fetch → fails; the isolated-try/except passes |
| `test_always_on_records_under_sandbox` | with `environment='sandbox'` set in config AND an active context → a row IS recorded | proves NO sandbox gate (LOCK 3) — a copied `_step_schwab_*` short-circuit would record 0 → fails |
| `test_update_call_outcome_preserves_pk` (repo) | insert → id; update → same id; re-read by id → updated fields | a stray `INSERT OR REPLACE` reassigns the AUTOINCREMENT PK → fails |
| `test_migration_0030_*` (Task 0) | table/columns/indexes/CHECKs; migrate-twice no-op; backup-gate strict equality; `EXPECTED_SCHEMA_VERSION == 30` | — |
| `test_runner_sets_and_clears_context` (Task 5) | context active mid-run with the real run_id + `surface='pipeline'`; `None` after the run's `finally` | proves set + the `finally` clear (no stale context bleeding across runs in a long-lived process) |
| `test_labeling_records_download_single` / `test_price_cache_records_download_intraday` (Task 6) | the two remaining sites record under a `cli`/`pipeline` context | proves full enumeration coverage (#27 no silent skip) |

---

## Risks / deviations / V1 simplifications

- **Site-4 (price_cache intraday) enum + scope** — flagged to CHARC above (the §enumeration flag). Default = wrap it with a new `'download_intraday'` `call_type`; CHARC may keep it OUT (drop Task 6's price_cache wrap + the enum value). **STOP-and-confirm before executing Task 6** if the orchestrator/CHARC has not ruled.
- **Web-dashboard live-price fetches NOT audited in V1** — they have no clean run boundary to scope a context; an unset context = no-op (correct, not a silent skip — the call still runs, just unrecorded). The pipeline open-trade warm path IS audited (it runs under the runner's `'pipeline'` context). V2: a web-request-scoped context (mirroring `SWING_WEB_REQUEST_ID` / `log_correlation`). Documented in Task 6.
- **`rows_returned` for batch = `len(raw)` (the multi-index frame's row count)**, NOT the sum of per-ticker extracted rows — this is the count yfinance returned, which is the right observability signal (the per-ticker extraction is a downstream concern). Documented at the wrap.
- **Audit opens a short-lived connection per chokepoint call** — unlike the pipeline's single shared `audit_conn`, the chokepoints can't share one (no threaded conn). Volume is ~10–15 calls/night (§Volume), so the per-call `connect()` cost is negligible, and `_AUDIT_WRITE_LOCK` + `BEGIN IMMEDIATE` serialize writes correctly across connections (the audit_service docstring confirms cross-connection serialization). The serial single-fetch loop opens/closes a conn per ticker only on warm-MISS tickers (the warm batches the rest into ONE batch row).

## Volume + retention (per brief — noted, NOT this arc)

A batch call = ONE row (not per-ticker), so nightly volume ≈ the warm's chunk count + warm-miss single fallbacks + open-trade intraday warms ≈ 10–15 rows/night, the same order as `schwab_api_calls`. Per-call granularity is affordable. A long-term prune (mirroring `swing logs cleanup` / the exports archiver) is future hygiene, NOT 18-C.

## R1 (`requests` dep) — does NOT ride this arc (per brief §6 + §10)

18-C adds NO dependency (yfinance + sqlite already declared) and does NOT touch `pyproject.toml`. R1 (the `requests` declaration) needs its own tiny dispatch or a later pyproject-touching host. Do not fold it in.
