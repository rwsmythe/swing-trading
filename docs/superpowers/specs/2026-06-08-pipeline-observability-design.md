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
def configure_logging(
    logs_dir: Path, *, surface: str, level: int = logging.INFO,
    formatter: logging.Formatter | None = None,
) -> None:
    """Attach a TimedRotatingFileHandler writing f'{surface}.log' to the root logger.
    Idempotent (dedup by baseFilename). surface in {'web','pipeline'}.
    `formatter` overrides the default formatter for this surface's handler — the
    seam stays Schwab-agnostic; the CLI injects a RedactingFormatter for the
    pipeline surface (see §4.2). The formatter is set on the handler BEFORE the
    handler is added to root, so there is no unredacted window."""
```

- Filename: `logs_dir / f"{surface}.log"`. Same handler config as today's `configure_web_logging`:
  `TimedRotatingFileHandler(filename, when="D", interval=1, backupCount=7, encoding="utf-8")`,
  default formatter `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"` when `formatter is None`,
  `root.setLevel(level)`.
- **Idempotent**: skip handler creation if a `TimedRotatingFileHandler` with the same `baseFilename`
  already on root (preserves the pytest handler-leak protection that the current dedup provides).
  **But when `formatter` is supplied and a same-file handler already exists** (R2-Major-2 fix), do NOT
  silently return with the old formatter in place — call `existing.setFormatter(formatter)` so the
  redacting formatter is guaranteed installed on the pipeline surface even if a prior
  `configure_logging(surface="pipeline")` (or a test) attached a default-formatter handler first. A
  test asserts that a pre-existing default-formatter `pipeline.log` handler ends up carrying the
  `RedactingFormatter` after a second call supplies it.
- The `formatter` injection point is the ONLY Schwab-aware seam touch and it is a *parameter*, not
  baked-in logic — `configure_logging` itself imports nothing from `swing.integrations.schwab`. The
  CLI (the secret-bearing surface) owns constructing + passing the redacting formatter.
- `configure_web_logging(logs_dir)` becomes a **thin shim**: `configure_logging(logs_dir,
  surface="web")` (no formatter override → default formatter). The [app.py:441](../../../swing/web/app.py)
  call site and every existing `web.log` test are preserved unchanged.

> **Seam scope guard:** this arc adds ONLY the `surface`/`level` parameterization + the second
> consumer. Retention, a configurable level knob, log-volume right-sizing, and web↔subprocess
> correlation are **Arc-2a/2b** — do not build them here. `level` exists so Arc-2a can wire a knob
> without changing the signature; default stays `INFO`.

### 4.2 Subprocess entrypoint wiring

**Redaction is two belts, by design — the factory alone is NOT sufficient for `pipeline.log`.** The
process-global `setLogRecordFactory` redacts only records whose logger name starts with the
schwabdev prefix (capital-S `"Schwabdev"`). But `pipeline.log` also carries `swing.*` records and
**exception tracebacks** — e.g. a `swing.integrations.schwab.*` wrapper logging `log.warning("schwab
failed: %s", exc)` where `exc` carries a token/accountHash in its args, or an unhandled traceback
through a `swing.pipeline.*` logger. The Schwabdev-prefix factory would NOT redact those. So the
pipeline surface gets a second belt:

- **Belt A — process-global factory:** `ensure_schwab_log_redaction_factory_installed()` (covers
  Schwabdev-origin records at creation; shared with the web surface).
- **Belt B — `RedactingFormatter` on the `pipeline.log` handler:** a `logging.Formatter` subclass
  whose `format()` applies the existing content-redactor to the **fully rendered line** returned by
  `super().format(record)` — i.e. message + interpolated args + traceback + stack-info, **regardless
  of logger name**. This is the authoritative guarantee for `pipeline.log`; it cannot be bypassed by
  a non-Schwabdev logger or a traceback because every record the handler writes passes through its
  formatter. Because the formatter is set on the handler **before** the handler is added to root
  (§4.1), there is no window in which an unredacted line reaches the file.
  - **Live redactor, consulted per record (R2-Major-1 fix):** `format()` builds the redactor via
    `_make_redactor_from_global()` **on every call** (exactly as the existing factory does per-record
    at [client.py:170](../../../swing/integrations/schwab/client.py)), so a secret registered or
    rotated **after** handler attachment is still redacted; the 32+hex / 24+b64 heuristic catches
    token/hash *shapes* even for a slot not yet registered. A test plants a secret that becomes known
    only AFTER the handler is attached and asserts it is still redacted in `pipeline.log`.

Wiring in `pipeline_run_cmd` ([cli.py:3210](../../../swing/cli.py)), **before** `run_pipeline(...)`,
in this order:

1. `ensure_schwab_log_redaction_factory_installed()` — Belt A, installed FIRST (before any handler
   attach or emit). Process-global + idempotent.
2. `configure_logging(cfg.paths.logs_dir, surface="pipeline", formatter=RedactingFormatter(...))` —
   attaches the child-side `pipeline.log` handler carrying Belt B. Works for both web-spawned
   (DEVNULL parent) and direct `swing pipeline run` invocation.

This order (factory then handler) means the very first line written to `pipeline.log` is already
covered by both belts. `RedactingFormatter` lives in the Schwab integration package (it depends on
the redactor); the CLI imports it and passes it in, keeping `configure_logging` Schwab-agnostic.

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

**Semantic contract (binding — writing-plans must audit all 13 call sites against it):**
`lease.step(name)` is called **at the start of `name`'s work**, immediately before that step's body.
The captured duration of step `name` is the wall-clock/monotonic interval from its `step(name)` call
to the **next distinct** `step(...)` call (or to flush, for the final step). Therefore the table
records **step-boundary intervals**, not isolated step bodies — any gap (cleanup, between-step
overhead) is attributed to the step that owns the *preceding* boundary. Pre-first-step bootstrap
(lease acquisition, finviz inbox `mkdir`, `select_csv` at [runner.py:593-634](../../../swing/pipeline/runner.py))
runs **before** the first `step("finviz_fetch")` and is intentionally **outside** step timing — it is
sub-second startup, not pipeline work, and the ~570s attribution problem lives entirely inside the
step sequence. (If a future need arises to time bootstrap, that is a separate concern, not this arc.)

`lease.step(name)` (its existing `update_step` DB write is **unchanged**) additionally:

1. **Consecutive same-step collapse:** if `_pending` exists and `_pending.step_name == name` →
   **ledger no-op** (still performs the existing idempotent `update_step`). This rule is intentionally
   narrow: it collapses **consecutive duplicate marker calls for the currently-open step** (the known
   `finviz_fetch` double-fire at [runner.py:634/758](../../../swing/pipeline/runner.py), where the
   actual fetch happens between/around the two markers — collapsing yields ONE correct
   `finviz_fetch` interval spanning all the work). The pipeline is **strictly linear** — no step is
   re-entered after a *different* step runs — so this rule never hides legitimately-separate work.
   A future step needing sub-step timing is out of scope (would use its own intra-step instrument,
   not this boundary ledger).
2. Else (a distinct new step): **close** `_pending` (`finished_ts = _now_iso()`,
   `duration_ms = int((monotonic_now − _pending.monotonic_start) * 1000)` — integer truncation, not
   `round()`, to keep duration arithmetic unsurprising at sub-ms/0ms boundaries), append to
   `_timings`; **open** a new `_pending = (ordinal=_next_ordinal++, name, started_ts=_now_iso(),
   monotonic_start=monotonic_now)`.
3. On close, emit the **per-step log line** (see §5.4).

The ledger fields are initialized in `Lease.__init__` (empty `_timings`, `_pending=None`,
`_next_ordinal=0`, `_timings_flushed=False`), so the ledger always exists for any constructed `Lease`.
Monotonic clock: `time.monotonic()`. `started_ts`/`finished_ts` are wall-clock `_now_iso()` (ISO
seconds) — used for human reading + inter-step gap analysis only; `duration_ms` is the authoritative
precise duration.

### 5.2 Flush: once, in `run()`'s `finally`

`run()`'s `finally` block ([runner.py:1034](../../../swing/pipeline/runner.py)) calls
`lease.flush_step_timings()`. **`lease` is always bound at this finally:** `acquire_lease` runs in
the *outer* try ([runner.py:560-572](../../../swing/pipeline/runner.py)) whose `except
ConcurrentRunBlockedError` **returns at L572 — before** the big `try`/`finally` (L586/L1034) is ever
entered; so the finally only runs when `lease` already exists. (Writing-plans: keep this invariant —
if any future refactor moves `acquire_lease` inside the big try, add an explicit `lease = None`
sentinel + `if lease is not None:` guard.)

`flush_step_timings()`:

- **Idempotent flush-once** via `_timings_flushed`, but the guard is **set `True` only AFTER the
  batch insert transaction commits** (R2-Major-3 fix) — a transient lock/disk error therefore does
  NOT permanently disable a later retry while the in-memory ledger still holds the data. Closing the
  final `_pending` sets `_pending = None`, so a re-entrant flush after a failed insert does not
  double-close or re-append; it simply retries the **whole single-transaction** insert. The batch is
  one `with conn:` transaction, so a failed attempt commits nothing (no partial rows). `ON CONFLICT
  DO NOTHING` (R3-Minor-2 clarification) is therefore NOT about partial commits within one
  transaction — it guards a re-flush by a **separate** `Lease`/process for the same `run_id` (already
  committed rows present) against a UNIQUE IntegrityError. Empty ledger → no-op (returns immediately).
- **Closes the final `_pending`** using "now", then writes **all** ledger rows. `complete` is the
  final `lease.step` and IS a real boundary interval: its duration measures the post-`export`
  finalization work — `_step_review_log_cadence` ([runner.py:1014-1020](../../../swing/pipeline/runner.py))
  plus `lease.release()` plus teardown up to the flush. It is small but **not fake**; `export` gets
  its own real duration from the `export`→`complete` boundary. (Do NOT special-case or drop
  `complete`; it is one of the 13 and carries genuine, if brief, work.)
- **Connection:** uses the project's `connect(db_path)` helper
  ([swing/data/db.py:65](../../../swing/data/db.py)) — NOT a bare `sqlite3.connect` — so the write
  inherits the uniform `busy_timeout=30s` + `foreign_keys=ON` + row-factory PRAGMAs. Wrapped in
  `contextlib.closing(connect(db_path))` + a single `with conn:` transaction (one INSERT-many).
  Independent, append-only child table; does NOT touch `pipeline_runs`, so it needs no lease fencing
  and adds **exactly one** transaction per run — not 13 — introducing **no new per-step
  lock-contention point** (respects the `database is locked` deadlock scars + the single-transaction
  `BEGIN IMMEDIATE` contract; CLAUDE.md §Gotchas/SQLite). The `busy_timeout` means a transient lock
  waits rather than failing fast.
- **Flush-failure degrades cleanly, never masks (Major-5 resolution):** the call site is
  `try: lease.flush_step_timings() except Exception as exc: log.error("step-timing flush failed: %s",
  exc)` — it **never re-raises from the finally** (so it cannot mask an in-flight exception
  propagating through the finally) and it **never blocks** run finalization (which already happened
  via `lease.release()`). The durable fallback is the **per-step log lines** (§5.4) already written to
  `pipeline.log` during the run — so even if DB persistence is lost (lock-timeout exhausted,
  disk-full, FK/connection error), the human-readable per-step attribution survives in the log. The
  test suite exercises a flush-failure (e.g. an unwritable/locked DB) and asserts (a) the original
  run outcome is unchanged, (b) an error is logged, (c) the per-step log lines are present.
- **force_cleared safety:** the `finally` runs even when the lease was revoked. The flush uses a
  fresh `connect()` (no lease token needed) and the `pipeline_runs` FK-target row still exists
  (`force_clear` sets state, does not delete) → partial timings persist. If the run never reached the
  big `try` (the `ConcurrentRunBlockedError` early return at L572 before any `lease.step`), there is
  nothing to flush (ledger empty) — no-op.

This satisfies the brief's "durations must persist (or degrade cleanly) when a run ends
failed/blocked/force_cleared mid-step — tie the flush to release()/finalize, not only the happy
path."

### 5.3 Persistence — migration `0025`, v24 → v25

The `0025_phase16_pipeline_step_timings.sql` file contains **PURE DDL only** — no `BEGIN`/`COMMIT`
in the file. Transaction control + the `foreign_keys=OFF` toggle are provided by the existing runner
`_apply_migration` ([swing/data/db.py:252-295](../../../swing/data/db.py)), which already does
`executescript(sql)` + `commit()` + `rollback()` on failure, with FK toggled OFF for the duration and
restored after. (Embedding `BEGIN`/`COMMIT` in the file would conflict with that wrapper — do NOT.)

```sql
-- 0025_phase16_pipeline_step_timings.sql  (pure DDL; runner wraps the transaction)
CREATE TABLE pipeline_step_timings (
  id          INTEGER PRIMARY KEY,
  run_id      INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
  ordinal     INTEGER NOT NULL,          -- 0-based order of this step within the run
  step_name   TEXT    NOT NULL,          -- free-text; no CHECK enum (future steps need no schema change)
  started_ts  TEXT    NOT NULL,          -- wall-clock ISO seconds (_now_iso) at step open
  finished_ts TEXT    NOT NULL,          -- wall-clock ISO seconds at step close (always set: flush closes before insert)
  duration_ms INTEGER NOT NULL,          -- monotonic-sourced, integer-truncated ms
  UNIQUE(run_id, ordinal)
);
-- No separate run_id index (R2-Minor-3): the UNIQUE(run_id, ordinal) constraint already
-- creates an index with run_id as the leading column, which SQLite uses for run_id lookups.
```

- **`finished_ts` / `duration_ms` are `NOT NULL`** (Minor-1 resolution): the flush ALWAYS closes the
  final `_pending` before inserting, and every other ledger entry was closed at its boundary — so no
  un-closed row is ever inserted. `NOT NULL` enforces that invariant and simplifies the read path.
- **No CHECK enum on `step_name`** (deliberate): keeps a future 14th step from needing a schema
  change. Because there is no enum, there is no schema-CHECK / Python-constant / dataclass-validator
  triad to keep atomic for `step_name`. (The #11 discipline still applies to the read-path: the new
  `StepTiming` dataclass + its `_row_to_step_timing` mapper land in the **same task** as the
  write-path repo function.)
- **`ON DELETE CASCADE`**: a safety net (pipeline_runs rows are effectively append-only history,
  rarely deleted). Inert if `PRAGMA foreign_keys` is OFF; active under the runtime `connect()`
  (`foreign_keys=ON`) — harmless either way.
- **Idempotent insert (Major-9 resolution):** the batch insert uses
  `INSERT INTO pipeline_step_timings (...) VALUES (...) ON CONFLICT(run_id, ordinal) DO NOTHING`, so a
  re-flush (a second `Lease` object for the same `run_id`, a process retry) cannot raise a UNIQUE
  IntegrityError — the first write wins, the table stays append-only. A test asserts a repeated flush
  against existing rows is a harmless no-op.
- **Migration-runner discipline (#9):** the `0025` file is pure DDL; `_apply_migration` supplies the
  explicit transaction + `rollback()` + FK toggle. Do NOT bare-`executescript` from elsewhere.
- **Backup gate (Major-8 resolution) — a backup TRIGGER, not a block.** Add a new
  `_phase16_backup_gate(conn, *, current_version, target_version, backup_dir)` mirroring the
  established per-phase shape ([_b7_backup_gate, db.py:1029-1066](../../../swing/data/db.py)): fire
  ONLY when `current_version == 24 AND target_version >= 25` (STRICT equality on `current_version`
  per the `pre_version == (target-1)` gotcha), take a `Connection.backup()` snapshot
  (`swing-pre-phase16-migration-<ISO>.db`) + `_verify_backup_integrity` against
  `PHASE16_PRE_MIGRATION_EXPECTED_TABLES` (= the **v24/B-7** table set, i.e. the *pre*-migration set,
  which does NOT yet include `pipeline_step_timings`). Wire it into `run_migrations`
  ([db.py:1141](../../../swing/data/db.py)) right after `_b7_backup_gate`. Semantics: it does not
  BLOCK — it snapshots before crossing v25. A v24→v26 walk trips it (backup taken, correct — you are
  crossing v25); a v25→v26 walk leaves it inert (`current_version != 24`). Tests cover v24→v25
  (backup), v24→v26 (backup), v25→v26 (inert).
- **Migrate-twice no-op test** through the real runner path (second run is a no-op:
  `current >= target` early-returns at [db.py:1090](../../../swing/data/db.py)).

### 5.4 Slow-step log lines — promote charts-only warning to all steps

On each ledger close (§5.1 step 3) and the final flush close, **always** emit an `INFO` per-step line
via the pipeline logger, e.g. `INFO  step {step_name} took {duration_ms} ms` — this is the durable
human-readable attribution (and the fallback if DB flush fails, §5.2). Additionally, a **single
coarse advisory soft-budget** (default the charts 60s shape) emits a `WARN` when a step exceeds it —
purely informational, NOT a control-flow gate and NOT an error. Rationale for advisory-only (Minor-3
resolution): some steps are naturally long (`charts`, `export`, `evaluate`), so a uniform hard-ERROR
threshold would be noisy/misleading; per-step budgets can be tuned later **without schema churn**
(budgets are constants, not persisted). The exact soft-budget value is a writing-plans detail. The
**existing charts-specific warning at [runner.py:3214-3226](../../../swing/pipeline/runner.py) stays
unchanged** (it carries charts-specific `scope=tickers` context); the generic per-step line is
additive, not a replacement.

### 5.5 Repo + dataclass surface

- New `swing/data/repos/pipeline_step_timings.py` (or fold into the existing
  `swing/data/repos/pipeline.py`): `insert_step_timings(conn, run_id, timings: Sequence[StepTiming])`
  batch insert; `list_step_timings(conn, run_id) -> list[StepTiming]` (with an explicit
  `ORDER BY ordinal ASC` — R2-Minor-2; SQLite does not guarantee row order otherwise) for the perf
  follow-on + tests.
- New `StepTiming` dataclass (frozen) + `_row_to_step_timing` mapper, landing in the same task as the
  repo (read-path/write-path together).

---

## 6. Things to nail — test contracts

Each is a binding contract for writing-plans; TDD per task.

1. **Redaction proven on `pipeline.log` via BOTH belts (not assumed).** With the pipeline-surface
   logging configured (factory + `RedactingFormatter`), plant secret-shaped sentinels and assert
   each is **redacted in the written `pipeline.log` file**, specifically covering the cases the
   Schwabdev-prefix factory alone would MISS: (a) a sentinel logged through a **non-Schwabdev logger
   name** (e.g. a `swing.pipeline.*` logger) and (b) a sentinel embedded in an **exception
   traceback** (`log.error("...", exc_info=True)` where the exception args carry the sentinel). Both
   must come out redacted — proving Belt B (the formatter), not just Belt A. Also assert the handler
   carries the `RedactingFormatter` at attach time (no unredacted window). **And (R3-Minor-1) cover
   the late-known-secret case in this binding checklist:** a secret registered/rotated **after**
   handler attachment is still redacted in `pipeline.log` (proves `format()` consults the live
   redactor per record, §4.2). Extends the `tests/integrations/test_schwab_client.py`
   `*_does_not_leak_account_hash` family to the new file surface.
2. **Discriminating duration persistence** (`feedback_regression_test_arithmetic`): drive a run (or a
   `Lease` unit harness) where one step is fast and one is injected-slow; assert the persisted
   `duration_ms` values **distinguish** them (slow.ordinal duration > fast.ordinal duration by the
   injected margin) — NOT merely "a row exists." Compute the expected ordering under both a correct
   and a naive (overwrite/last-wins) implementation to confirm the test fails on the naive one.
3. **Idempotent same-step re-fire:** a `Lease` that receives `step("finviz_fetch")` twice in a row
   produces **one** `finviz_fetch` ledger row, not two (the double-fire at runner.py:634/638).
4. **Terminal-state coverage:** a run that ends `failed` mid-step **and** one force_cleared mid-step
   each persist partial timings (flush in `finally`). force_cleared: assert rows written via the
   fresh `connect()` despite lease revocation.
4b. **Flush-failure degrades cleanly (Major-5):** with the timings table made unwritable (e.g. a
   stubbed flush that raises, or a locked DB), assert (a) the run's `RunResult` outcome is unchanged
   (flush failure does not alter completion/failure), (b) an error is logged, (c) the original
   in-flight exception — if any — is NOT masked by the flush exception, and (d) the per-step `INFO`
   log lines are still present in `pipeline.log`.
4c. **Idempotent re-flush (Major-9):** calling the flush twice for the same `run_id` (second time via
   a fresh `Lease`/ledger replaying the same ordinals) inserts no duplicate rows and raises no
   IntegrityError (`ON CONFLICT(run_id, ordinal) DO NOTHING`).
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
       ├─ ensure_schwab_log_redaction_factory_installed()    ── Belt A FIRST (before any handler/emit)
       ├─ configure_logging(logs_dir, surface="pipeline",     ── attaches pipeline.log handler
       │                    formatter=RedactingFormatter())      carrying Belt B (redacts every line)
       └─ run_pipeline
            └─ run()
                 ├─ acquire_lease  → Lease (with empty ledger)
                 ├─ lease.step("finviz_fetch") … "complete"   ── each transition:
                 │     • existing update_step DB write (unchanged)
                 │     • ledger: close prev (duration_ms via monotonic), open new
                 │     • INFO per-step duration line (+ advisory WARN if over soft-budget)
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
- **Slow-step threshold** (§5.4): pick the single advisory soft-budget constant (default the charts
  60s shape) — INFO per-step always, WARN above the soft budget; no hard-ERROR threshold. Log-severity
  only, not control flow.
- **Ledger location decision** for writing-plans: ledger state lives on `Lease` (co-located with
  `step()`); confirm `flush_step_timings()` is the single public flush entry and is called exactly
  once from `run()`'s `finally` (guarded). Verify no other `lease.step` caller path bypasses the
  finally.
- **`complete` boundary semantics** (§5.2): the final `lease.step("complete")` opens a pending entry
  closed at flush; its `duration_ms` measures genuine post-`export` finalization work
  (`_step_review_log_cadence` + `release` + teardown). It is small but real — the table records
  step-boundary intervals, and `complete` is one of the 13. Document in the plan that a brief
  `complete` duration is expected, not a bug; do NOT special-case or drop it.
- **Repo home:** decide new `swing/data/repos/pipeline_step_timings.py` vs folding into
  `swing/data/repos/pipeline.py` (lean: separate file for a focused unit).
```
