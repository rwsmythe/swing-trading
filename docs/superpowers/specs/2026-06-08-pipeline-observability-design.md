# Design Spec — Phase 16 / Arc 1: Pipeline-Run Observability

**Status:** LOCKED (brainstorming converged). **Date:** 2026-06-08.
**Cycle:** `copowers:brainstorming` → (next) `copowers:writing-plans` → `copowers:executing-plans`.
**Schema:** v24 → **v25** (migration `0025`). **Branch-from:** main HEAD at worktree creation.
**Brief:** `docs/arc1-pipeline-observability-brainstorming-dispatch-brief.md`.

---

## 1. Problem & mandate

web-Run #96 (2026-06-08) took ~10m25s; Schwab calls were only ~25.5s, leaving ~570s of
pre-Schwab (yfinance-bound) work with **zero timing visibility** — and *unloggable*, because the
web-spawned pipeline subprocess discards stdout/stderr (`stdout=DEVNULL, stderr=DEVNULL`,
[`swing/web/routes/pipeline.py:127-131`](../../../swing/web/routes/pipeline.py)). Error messages
already tell operators to "check `swing-data/logs/pipeline.log`" — **a file that is never created.**

Mandate, two halves:

- **1a — `pipeline.log` survives.** The pipeline subprocess configures its **own** rotating file
  handler (independent of the DEVNULL'd parent), with Schwab secret redaction **guaranteed** on
  that surface.
- **1b — per-step DURATION capture** (log line **and** DB persistence) across **all 13** pipeline
  steps, so the next slow run answers "which step owns the time" outright instead of by inference.

This arc **measures**. It does NOT fix performance, does NOT do the Arc-2 logging overhaul, does NOT
do the 1c yfinance call-timing audit. See §9.

---

## 2. Grounded current state (verified on HEAD)

- **Subprocess spawn:** [`swing/web/routes/pipeline.py:121-131`](../../../swing/web/routes/pipeline.py)
  runs `python -m swing.cli --config <path> pipeline run --manual` with
  `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True`.
- **CLI entrypoint:** [`swing/cli.py:3210-3228`](../../../swing/cli.py) `pipeline_run_cmd` applies
  config overrides and calls `run_pipeline`. It configures **no logging** and installs **no
  redaction factory**.
- **Existing file-log template:** `configure_web_logging(logs_dir)`
  ([`swing/web/middleware/request_id.py:32-50`](../../../swing/web/middleware/request_id.py)) — a
  `TimedRotatingFileHandler` (`when="D"`, `interval=1`, `backupCount=7`, `encoding="utf-8"`),
  formatter `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`, idempotent dedup by
  `baseFilename`, root logger at `INFO`. Called from [`swing/web/app.py:441`](../../../swing/web/app.py)
  as `configure_web_logging(cfg.paths.logs_dir)`. `cfg.paths.logs_dir` exists
  ([`swing/config.py:14`](../../../swing/config.py)).
- **Redaction factory:** `ensure_schwab_log_redaction_factory_installed()`
  ([`swing/integrations/schwab/client.py:201-221`](../../../swing/integrations/schwab/client.py)) —
  a process-global `logging.setLogRecordFactory` wrapper, idempotent, re-wraps if another library
  replaced it, redacts records whose logger name starts with the schwabdev prefix (capital-S
  `"Schwabdev"`). The pipeline subprocess makes Schwab calls (`schwab_snapshot`, `schwab_orders`
  steps) → `pipeline.log` could leak token/accountHash without it installed.
- **Step model:** **13** `lease.step(name)` transitions in
  [`swing/pipeline/runner.py`](../../../swing/pipeline/runner.py):
  `finviz_fetch, weather, evaluate, daily_management, watchlist, recommendations, pattern_detect,
  pattern_observe, schwab_snapshot, schwab_orders, charts, export, complete`. `lease.step()`
  ([`swing/pipeline/lease.py:53-62`](../../../swing/pipeline/lease.py)) opens its OWN connection +
  `with conn:` transaction and calls `update_step(...)`, rewriting `pipeline_runs.current_step` +
  `last_step_progress_ts` (overwritten each transition — never captured).
  - **`finviz_fetch` fires from TWO sites** for one run ([runner.py:634](../../../swing/pipeline/runner.py)
    and [runner.py:638's neighborhood](../../../swing/pipeline/runner.py); see also L758) — the
    capture mechanism MUST be idempotent against same-step re-fire (no double-row).
- **`_now_iso()`** ([lease.py:28-29](../../../swing/pipeline/lease.py)) =
  `datetime.now().isoformat(timespec="seconds")` — **seconds-precision wall-clock**, too coarse to
  be the *duration* source; durations come from a monotonic clock (§5).
- **`pipeline_runs` DDL** ([`0003_phase2_pipeline_trades.sql:120-143`](../../../swing/data/migrations/0003_phase2_pipeline_trades.sql)):
  per-step STATUS as discrete columns for only **6** of 13 steps
  (`weather_status`/`evaluation_status`/`watchlist_status`/`recommendations_status`/`charts_status`/`export_status`).
  **No per-step duration anywhere.**
- **Charts-only slow-step warning:** [`runner.py:3214-3226`](../../../swing/pipeline/runner.py)
  computes `_walltime_elapsed` and warns >60s / errors >120s — for the **charts step only** today.
- **Terminal exit paths:** every path (complete, failed-early-return, force_cleared, exception)
  passes through `run()`'s `finally` ([runner.py:1034-1038](../../../swing/pipeline/runner.py)). The
  force_cleared path ([runner.py:1025-1033](../../../swing/pipeline/runner.py)) cannot call
  `lease.release()` (lease revoked); `force_clear` sets `state='force_cleared'` — it does NOT delete
  the `pipeline_runs` row, so a child-table FK target survives.

---

## 3. Resolved open questions (operator-signed 2026-06-08)

| OQ | Decision | Why |
|----|----------|-----|
| **OQ-1 — Arc-1/Arc-2 seam** | **Pull the seam forward.** Create `configure_logging(logs_dir, *, surface, level=INFO)`; route BOTH `web.log` and `pipeline.log` through it. | Born-right; avoids throwaway + a second edit of the redaction-critical subprocess entrypoint in Arc-2a. Operator chose full-cycle to settle the seam up front. |
| **OQ-2 — persistence shape** | **`pipeline_step_timings` child table** (not wide columns). | Scales to all 13 steps + future steps; queryable for the perf follow-on; does not churn the wide `pipeline_runs` table. |
| **OQ-3 — granularity/units** | **`duration_ms` INTEGER (monotonic-sourced) + per-step `started_ts` & `finished_ts` (wall-clock ISO seconds).** | Integer ms avoids float-compare fragility; timestamps enable inter-step gap analysis; `duration_ms` is the denormalized cheap-query column. |
| **OQ-4 — rotation/format** | **Match `web.log`** (`TimedRotatingFileHandler`, `when="D"`, `backupCount=7`, utf-8, same formatter), via the shared seam. | Lowest-surprise; retention/right-sizing is explicitly Arc-2b; the seam signature leaves room to swap policy centrally later. |

**Central design Q3 (capture mechanism — implementer's call within fence/lock discipline):**
**monotonic in-memory ledger on the `Lease`, flushed once at finalize** (NOT a per-`lease.step()`
write). See §5.

---

## 4. Component 1a — `pipeline.log` + redaction

### 4.1 The logging seam (new module)

New neutral module `swing/logging_config.py` (top-level so both `swing.web` and `swing.cli` can
import it without `swing.cli` importing web middleware or vice versa):

```python
def configure_logging(logs_dir: Path, *, surface: str, level: int = logging.INFO) -> None:
    """Attach a TimedRotatingFileHandler writing f'{surface}.log' to the root logger.
    Idempotent (dedup by baseFilename). surface in {'web','pipeline'}."""
```

- Filename: `logs_dir / f"{surface}.log"`. Same handler config as today's `configure_web_logging`:
  `TimedRotatingFileHandler(filename, when="D", interval=1, backupCount=7, encoding="utf-8")`,
  formatter `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`, `root.setLevel(level)`.
- **Idempotent**: skip if a `TimedRotatingFileHandler` with the same `baseFilename` already on root
  (preserves the pytest handler-leak protection that the current dedup provides).
- `configure_web_logging(logs_dir)` becomes a **thin shim**: `configure_logging(logs_dir,
  surface="web")`. The [app.py:441](../../../swing/web/app.py) call site and every existing
  `web.log` test are preserved unchanged.

> **Seam scope guard:** this arc adds ONLY the `surface`/`level` parameterization + the second
> consumer. Retention, a configurable level knob, log-volume right-sizing, and web↔subprocess
> correlation are **Arc-2a/2b** — do not build them here. `level` exists so Arc-2a can wire a knob
> without changing the signature; default stays `INFO`.

### 4.2 Subprocess entrypoint wiring

In `pipeline_run_cmd` ([cli.py:3210](../../../swing/cli.py)), **before** `run_pipeline(...)`, in this
order:

1. `configure_logging(cfg.paths.logs_dir, surface="pipeline")` — child-side file handler. Works for
   both web-spawned (DEVNULL parent) and direct `swing pipeline run` invocation.
2. `ensure_schwab_log_redaction_factory_installed()` — installed **before the first log emit** so no
   `pipeline.log` line can carry a Schwab token/accountHash. (The factory only mutates records whose
   logger name starts with the schwabdev prefix, but installing it first is the belt-and-suspenders
   mandate; it is process-global + idempotent.)

The web spawn **keeps `stdout=DEVNULL, stderr=DEVNULL`** — the child is self-contained via its file
handler; keeping DEVNULL avoids any pipe-buffer back-pressure on the parent. (Brief §5 "possibly
just removing DEVNULL" is resolved to: do NOT remove it.)

### 4.3 Windows / encoding

File handler `encoding="utf-8"`. No non-ASCII glyphs in any new operator-facing string (CLI stdout
cp1252 footgun). The CLI already reconfigures `sys.stdout/stderr` to utf-8 with `errors="replace"`
([cli.py:23-24](../../../swing/cli.py)) as the console safety net; the file handler is independently
utf-8.

---

## 5. Component 1b — per-step duration capture & persistence

### 5.1 Capture: monotonic ledger on the `Lease`, single flush at finalize

`Lease` ([lease.py:36](../../../swing/pipeline/lease.py)) gains in-memory ledger state (NOT
persisted per transition):

- `_timings: list[StepTiming]` — closed entries.
- `_pending: _PendingStep | None` — the currently-open step: `(ordinal, step_name, started_ts,
  monotonic_start)`.
- `_next_ordinal: int` (0-based).
- `_timings_flushed: bool` (flush-once guard).

`lease.step(name)` (its existing `update_step` DB write is **unchanged**) additionally:

1. If `_pending` exists and `_pending.step_name == name` → **ledger no-op** (idempotent against the
   `finviz_fetch` double-fire) — but still performs the existing `update_step` (already idempotent).
2. Else: **close** `_pending` (set `finished_ts = _now_iso()`,
   `duration_ms = round((monotonic_now − _pending.monotonic_start) * 1000)`), append to `_timings`;
   **open** a new `_pending = (ordinal=_next_ordinal++, name, started_ts=_now_iso(),
   monotonic_start=monotonic_now)`.
3. On close, emit the **slow-step log line** (see §5.4).

Monotonic clock: `time.monotonic()`. `started_ts`/`finished_ts` are wall-clock `_now_iso()` (ISO
seconds) — used for human reading + inter-step gap analysis only; `duration_ms` is the authoritative
precise duration.

### 5.2 Flush: once, in `run()`'s `finally`

`run()`'s `finally` block ([runner.py:1034](../../../swing/pipeline/runner.py)) calls
`lease.flush_step_timings()`:

- Guarded by `_timings_flushed` (idempotent — safe if both a future explicit call and the finally
  fire).
- **Closes the final `_pending`** using "now" (so the last real step — `complete` is the final
  `lease.step`, but `complete` is itself a pseudo-step; its open entry is closed at flush, giving the
  preceding `export`→`complete` boundary a real duration for `export` and a short/near-zero duration
  for `complete`).
- Writes **all** ledger rows in **ONE transaction** on a **plain connection** (`connect(db_path)` +
  `with conn:`), NOT a `fenced_write` and NOT `lease.step()`'s connection. Rationale: the table is an
  independent, append-only, write-once-per-run child table; it does not touch `pipeline_runs`, so it
  needs no lease fencing and adds **exactly one** transaction per run — not 13 — introducing **no new
  per-step lock-contention point** (respects the `database is locked` deadlock scars + the
  single-transaction `BEGIN IMMEDIATE` contract; CLAUDE.md §Gotchas/SQLite).
- **force_cleared safety:** the `finally` runs even when the lease was revoked. The flush uses a
  plain connection (no lease token needed) and the `pipeline_runs` FK-target row still exists
  (`force_clear` sets state, does not delete) → partial timings persist. If the run never reached the
  big `try` (e.g. `ConcurrentRunBlockedError` returned at [runner.py:572](../../../swing/pipeline/runner.py)
  before any `lease.step`), there is nothing to flush (ledger empty) — flush is a no-op.

This satisfies the brief's "durations must persist (or degrade cleanly) when a run ends
failed/blocked/force_cleared mid-step — tie the flush to release()/finalize, not only the happy
path."

### 5.3 Persistence — migration `0025`, v24 → v25

```sql
-- 0025_phase16_pipeline_step_timings.sql
CREATE TABLE pipeline_step_timings (
  id          INTEGER PRIMARY KEY,
  run_id      INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
  ordinal     INTEGER NOT NULL,          -- 0-based order of this step within the run
  step_name   TEXT    NOT NULL,          -- free-text; no CHECK enum (future steps need no schema change)
  started_ts  TEXT    NOT NULL,          -- wall-clock ISO seconds (_now_iso)
  finished_ts TEXT,                      -- NULL only if flush could not close it (should not happen)
  duration_ms INTEGER,                   -- monotonic-sourced; NULL iff finished_ts NULL
  UNIQUE(run_id, ordinal)
);
CREATE INDEX ix_pipeline_step_timings_run ON pipeline_step_timings(run_id);
```

- **No CHECK enum on `step_name`** (deliberate): keeps a future 14th step from needing a schema
  change. Because there is no enum, there is no schema-CHECK / Python-constant / dataclass-validator
  triad to keep atomic for `step_name`. (The #11 discipline still applies to the read-path: the new
  `StepTiming` dataclass + its `_row_to_step_timing` mapper land in the **same task** as the
  write-path repo function.)
- **`ON DELETE CASCADE`**: a safety net (pipeline_runs rows are effectively append-only history,
  rarely deleted). Inert if `PRAGMA foreign_keys` is OFF at runtime — harmless either way.
- **Migration-runner discipline (#9):** explicit `BEGIN` + `executescript` + `COMMIT` with
  try/except `rollback()` + re-raise, `foreign_keys=OFF` at the runner level — copy the established
  `swing/data/db.py:_apply_migration` path; do NOT bare-`executescript`.
- **Backup gate STRICT equality (#11 family):** `pre_version == 24 AND target >= 25` — copy the
  Phase-9 clause shape; multi-version jumps stay separate two-step migrations.
- **Migrate-twice no-op test** through the real runner path.

### 5.4 Slow-step log lines — promote charts-only warning to all steps

On each ledger close (§5.1 step 3) and the final flush close, emit a per-step log line via the
runner/pipeline logger, e.g. `INFO  step {step_name} took {duration_ms} ms`. Promote the existing
charts soft/hard-budget pattern ([runner.py:3214-3226](../../../swing/pipeline/runner.py)) to a
generic per-step threshold: WARN above a soft budget, ERROR above a hard budget. Thresholds: reuse
the charts 60s/120s shape as the default per-step soft/hard budget (a single shared constant pair;
exact values are a writing-plans detail — they are a log-severity convenience, not a control-flow
gate). The **existing charts-specific warning at 3214-3226 stays** (it carries charts-specific
`scope=tickers` context); the generic per-step line is additive, not a replacement.

### 5.5 Repo + dataclass surface

- New `swing/data/repos/pipeline_step_timings.py` (or fold into the existing
  `swing/data/repos/pipeline.py`): `insert_step_timings(conn, run_id, timings: Sequence[StepTiming])`
  batch insert; `list_step_timings(conn, run_id) -> list[StepTiming]` for the perf follow-on +
  tests.
- New `StepTiming` dataclass (frozen) + `_row_to_step_timing` mapper, landing in the same task as the
  repo (read-path/write-path together).

---

## 6. Things to nail — test contracts

Each is a binding contract for writing-plans; TDD per task.

1. **Redaction proven on `pipeline.log` (not assumed).** Plant a non-token, secret-shaped sentinel
   through a pipeline log path with the factory installed (as the subprocess entrypoint installs it);
   assert the sentinel is **redacted in the written `pipeline.log` file**. Extends the
   `tests/integrations/test_schwab_client.py` `*_does_not_leak_account_hash` family to the new file
   surface. Assert the factory is installed **before** the first emit.
2. **Discriminating duration persistence** (`feedback_regression_test_arithmetic`): drive a run (or a
   `Lease` unit harness) where one step is fast and one is injected-slow; assert the persisted
   `duration_ms` values **distinguish** them (slow.ordinal duration > fast.ordinal duration by the
   injected margin) — NOT merely "a row exists." Compute the expected ordering under both a correct
   and a naive (overwrite/last-wins) implementation to confirm the test fails on the naive one.
3. **Idempotent same-step re-fire:** a `Lease` that receives `step("finviz_fetch")` twice in a row
   produces **one** `finviz_fetch` ledger row, not two (the double-fire at runner.py:634/638).
4. **Terminal-state coverage:** a run that ends `failed` mid-step **and** one force_cleared mid-step
   each persist partial timings (flush in `finally`). force_cleared: assert rows written via the
   plain connection despite lease revocation.
5. **Subprocess self-containment:** direct `swing pipeline run` (no web parent) writes `pipeline.log`
   with the per-step lines present.
6. **Migration round-trip:** migrate-twice no-op; backup gate strict `pre_version == 24`; the
   explicit `BEGIN/executescript/COMMIT/rollback` path exercised through the real runner.
7. **Seam regression:** `configure_web_logging` still produces `web.log` identically (existing
   web.log tests stay green); `configure_logging(surface="pipeline")` produces `pipeline.log`;
   idempotent dedup holds for both.
8. **Windows encoding:** file handler is utf-8; a subprocess-through-PowerShell stdout test for any
   new console echo path (none expected, but assert no non-ASCII in new strings).

---

## 7. Architecture & data flow (summary)

```
swing pipeline run  (subprocess; web-spawned w/ DEVNULL, or direct CLI)
  └─ pipeline_run_cmd
       ├─ configure_logging(logs_dir, surface="pipeline")   ── attaches pipeline.log handler
       ├─ ensure_schwab_log_redaction_factory_installed()    ── redaction BEFORE any emit
       └─ run_pipeline
            └─ run()
                 ├─ acquire_lease  → Lease (with empty ledger)
                 ├─ lease.step("finviz_fetch") … "complete"   ── each transition:
                 │     • existing update_step DB write (unchanged)
                 │     • ledger: close prev (duration_ms via monotonic), open new
                 │     • slow-step WARN/ERROR log line
                 ├─ lease.release(...)  (happy/failed)         ── pipeline_runs finalize (unchanged)
                 └─ finally:
                       └─ lease.flush_step_timings()           ── ONE plain-conn txn:
                             • close final pending
                             • batch INSERT all rows → pipeline_step_timings
                             (covers complete / failed / force_cleared / exception; idempotent)
```

Each unit is independently testable: `configure_logging` (pure handler attach), the `Lease` ledger
(in-memory, deterministic given a monotonic stub), the repo batch-insert (DB round-trip), the CLI
wiring (subprocess file presence + redaction).

---

## 8. Locks / invariants

- **Schema v24 → v25** — this cycle's single schema touch. DB stays OUTSIDE the Drive dir;
  `busy_timeout` unchanged.
- **Phase isolation:** change loci are `swing/logging_config.py` (new),
  `swing/web/middleware/request_id.py` (shim), `swing/cli.py` (entrypoint wiring),
  `swing/pipeline/lease.py` + `swing/pipeline/runner.py` (ledger + flush call),
  `swing/data/migrations/0025_*.sql` + the new repo/dataclass. `swing/web/routes/pipeline.py` is
  **unchanged** (DEVNULL kept). **`swing/trades/` stays read-only.**
- **No new per-step lock-contention point** — timing persistence is one batch transaction at
  finalize on a plain connection (§5.2).
- **Redaction factory** is installed in the subprocess entrypoint before any emit; the generic
  `configure_logging` seam stays Schwab-agnostic (redaction install is the CLI's explicit call, not
  baked into the logging module).
- **Discriminating tests** for timing persistence (§6.2) — assert the persisted value distinguishes
  fast vs slow, not just row existence.

---

## 9. Out of scope (explicit)

- **The Arc-2 logging overhaul** — centralized config beyond the seam, retention/cleanup of the
  logs dir, the level knob (the `level` param exists but is not wired to a knob here), volume
  right-sizing, web↔subprocess correlation. The seam is designed to host these later; they are NOT
  built now.
- **1c — yfinance call-timing audit** (deferred; likely its own schema). This arc's per-step
  `duration_ms` for the yfinance-bound steps (`weather`, `evaluate`, `charts`) is what *enables*
  deciding whether 1c is needed — flag, do not build.
- **The performance fix** (cap/parallelize/cache yfinance) — gated on the data THIS arc produces.
  Measuring is the whole point.
- **Arc 3 (XMAX thumbnail), Arc 4 (equity reconciliation).** No change to Schwab call logic itself —
  only its log-surface coverage.

---

## 10. Flagged for writing-plans

- **Task atomicity (#11):** `StepTiming` dataclass + `_row_to_step_timing` read-mapper land in the
  SAME task as the repo write function.
- **Slow-step thresholds** (§5.4): pick the shared soft/hard budget constants (default to the
  charts 60s/120s shape); they are log-severity only, not control flow.
- **Ledger location decision** for writing-plans: ledger state lives on `Lease` (co-located with
  `step()`); confirm `flush_step_timings()` is the single public flush entry and is called exactly
  once from `run()`'s `finally` (guarded). Verify no other `lease.step` caller path bypasses the
  finally.
- **`complete` pseudo-step duration semantics** (§5.2): the final `lease.step("complete")` opens a
  pending entry closed at flush; its `duration_ms` will be near-zero (it is a marker, not work). The
  preceding `export` gets its real duration from the `export`→`complete` boundary. Document this in
  the plan so a reviewer does not read the near-zero `complete` duration as a bug.
- **Repo home:** decide new `swing/data/repos/pipeline_step_timings.py` vs folding into
  `swing/data/repos/pipeline.py` (lean: separate file for a focused unit).
```
