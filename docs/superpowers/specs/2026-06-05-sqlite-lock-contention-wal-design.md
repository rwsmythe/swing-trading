# SQLite Lock-Contention (WAL + busy_timeout) — Brainstorm Design Spec

**Date:** 2026-06-05
**Phase:** 15 (post B-7 / PGT-redesign / pattern-observation-widening; schema **v24 holds**)
**Arc:** SQLite write-lock contention eliminating the silent Schwab→yfinance degrade
**Branch:** `sqlite-lock-contention-arc-brainstorm` (from main HEAD `cc353799`)
**Skill posture:** `copowers:brainstorming` (superpowers:brainstorming + adversarial Codex review to convergence)
**Status:** brainstorm SPEC — design only, NO code. Successor: `copowers:writing-plans`.
**Dispatch brief:** [`docs/sqlite-lock-contention-arc-brainstorming-dispatch-brief.md`](../../sqlite-lock-contention-arc-brainstorming-dispatch-brief.md)

---

## §0 Section map (for the return report)

- §1 Problem statement (confirmed symptom + amplifier)
- §2 **Grounded root cause** — incl. **Refinement R1 (the headline finding): WAL is ALREADY on; `busy_timeout` is the operative lever**; §2.4 the two contended paths' differing deadline regimes
- §3 Goals / non-goals (path-specific G1; G2' lock-wait visibility)
- §4 Proposed design (Approach A) — the centralized low-level opener (busy_timeout; WAL NOT reaffirmed on the hot path), observability + lock-wait fold-in, opener routing
- §5 Surfaces & blast radius decisions (dispatch brief §3)
- §6 Test strategy (discriminating, per `feedback_regression_test_arithmetic`)
- §7 Open questions for operator triage (OQ-0..OQ-E)
- §8 Locks / invariants preserved
- §9 Out of scope
- §10 Writing-plans readiness

---

## §1 Problem statement

The nightly pipeline OHLCV / quote fetch silently degrades to yfinance for ~13–22 liquid
tickers per run (SNAP, AMD, NVDA, COST, MSFT, NFLX, PLTR, AAPL, CRWD, …). Operator-witnessed
live on **2026-06-05** via a temporary instrumented catch-all in
[`swing/integrations/schwab/marketdata_ladder.py`](../../../swing/integrations/schwab/marketdata_ladder.py)
(since reverted). The captured exception was:

> `sqlite3.OperationalError: database is locked`

This IS the pre-existing banked **"Schwab market-data ladder T-C.1 wrapper erroring per-ticker →
yfinance fallback"** item (CLAUDE.md line-3), **amplified by #23** (the aplus→aplus+watch pool
widening multiplied the concurrent fetch count, raising sustained write pressure on the DB).

The degrade is invisible in `schwab_api_calls`: the lock failure raises **before** the audit
row commits, so it leaves no trace there. (The ~49 historical `pricehistory` ERROR rows are the
*separate* OhlcvBar-invariant bad-bar issue, ~2–4/run — distinct root cause; see §9.)

---

## §2 Grounded root cause (STEP-0 re-confirmed, discipline #2)

Every cited `file:line` was re-grounded in the worktree at HEAD `cc353799`.

### §2.1 The connection + concurrency model (confirmed)

1. The pipeline marketdata ladder is installed via `_build_pipeline_caches`
   ([`swing/pipeline/runner.py:347`](../../../swing/pipeline/runner.py)). The two hooks —
   `_quote_hook` ([runner.py:374](../../../swing/pipeline/runner.py)) and `_bars_hook`
   ([runner.py:417](../../../swing/pipeline/runner.py)) — **each open their OWN fresh
   `connect(cfg.paths.db_path)` connection per invocation** (runner.py:378 / :439), call the
   ladder, then `conn.close()`.
2. These hooks run **concurrently on a thread-pool executor**, bounded by
   `cfg.web.max_concurrent_ohlcv_fetches` (default **8**) and
   `cfg.web.max_concurrent_price_fetches` (default **8**) — [`swing/config.py:381,386`](../../../swing/config.py).
   So up to **16 concurrent writer connections** to the single DB file, plus other pipeline
   writers (candidates, OHLCV archive, evaluate).
3. Each ladder call → `get_price_history` / `get_quotes_batch` → audit-service
   `record_call_start` **and** `record_call_finish`. Each of those wraps its write in
   **`BEGIN IMMEDIATE`** ([`swing/integrations/schwab/audit_service.py:104,151`](../../../swing/integrations/schwab/audit_service.py)),
   which acquires the **write lock up front**. So each fetch issues **two** write-lock
   acquisitions.
4. The `database is locked` (SQLITE_BUSY) error — not a thread-affinity `ProgrammingError` —
   confirms **multiple connections contending**, exactly the model above.

### §2.2 Refinement R1 — THE HEADLINE FINDING: WAL is already ON; the dispatch brief's stated mechanism is incomplete

The dispatch brief §1 states the mechanism as:

> `connect()` opens `sqlite3.connect(db_path)` with **no `PRAGMA journal_mode=WAL`** → default
> rollback-journal mode, where every writer takes an **exclusive whole-DB lock**.

**STEP-0 grounding shows this is empirically false for the live DB.** Evidence:

- **Live DB header proves WAL.** Reading the first 100 bytes of `~/swing-data/swing.db`
  (zero-interaction header read, no connection opened): bytes 18 & 19 (the file-format
  write-version / read-version) are both **`2`** = WAL. (`1` would be a rollback-journal mode.)
  `magic = "SQLite format 3\x00"`, page_size 4096.
- **`journal_mode=WAL` is a PERSISTENT property of the database file**, recorded in the header.
  Once any connection sets it, the DB stays in WAL across all subsequent connections and across
  close/reopen, until explicitly changed. (SQLite docs: *"The WAL journaling mode is persistent;
  after being set it stays in effect across multiple database connections and after closing and
  reopening the database."*)
- **`ensure_schema()` already sets it.** [`swing/data/db.py:1132`](../../../swing/data/db.py)
  (`ensure_schema`, the `swing db-migrate` path) issues `PRAGMA journal_mode=WAL` on first open.
  The operator's DB reached v24 through this path → it was flipped to WAL persistently.
- **The codebase already assumes WAL.** [`swing/data/backup.py:8`](../../../swing/data/backup.py)
  design note: *"SQLite runs in WAL mode (PRAGMA journal_mode=WAL on first open)"* and uses the
  WAL-safe online backup API accordingly.

**Evidence tiering (Codex R1 minor #1).** Two of the four points are **repo-grounded invariants**
verifiable here and now: `ensure_schema` issues `PRAGMA journal_mode=WAL` (db.py:1132) and
`backup.py` documents+depends on WAL (backup.py:8). The header-byte read is **corroborating live
evidence** ("the operator's live DB was WAL on 2026-06-05"), not a repo invariant. The argument
does **not** rest on the live read alone: even without it, `connect()` only ever runs on a DB that
already passed through `ensure_schema` (it *raises* `SchemaVersionMismatchError` on a non-current /
fresh DB, db.py:1155–1167), and `ensure_schema` sets WAL persistently — so by construction every
DB `connect()` ever touches is already WAL. OQ-0 records the one-line live `PRAGMA journal_mode`
re-check as the operator confirmation.

**Therefore `connect()`'s lack of an explicit `PRAGMA journal_mode=WAL` does NOT put its
connections in rollback-journal mode** — they inherit the persistent WAL mode from the file
header. Adding `PRAGMA journal_mode=WAL` to `connect()` would be a **no-op on the live DB** and
would **not** fix the operator's problem — and reaffirming it on every hot-path open carries
needless risk (see §4.2 / Codex R1 major #1).

### §2.3 The ACTUAL mechanism (refined)

WAL relaxes reader/writer contention but **still permits exactly ONE writer at a time.** The
real failure chain:

1. Up to 16 concurrent fetch connections each issue **two `BEGIN IMMEDIATE`** write txns
   (start + finish). Under WAL these **serialize** on the single write lock.
2. **`connect()` ([db.py:1159](../../../swing/data/db.py)) sets no busy timeout.** It calls
   `sqlite3.connect(db_path)` with **no `timeout=` argument** and **no `PRAGMA busy_timeout`**
   (grep for `busy_timeout`/`timeout=` in `db.py` → **zero hits** in `connect()`). So the only
   ceiling in play is Python's implicit `sqlite3.connect` default of **`timeout=5.0`** (≈ a
   5000 ms busy handler).
3. SQLite's busy handler provides **no FIFO fairness** — it retries with backoff; under
   sustained contention a given writer can be **starved** while others jump the queue. #23's
   pool widening turned a brief burst into **sustained** write pressure, so a starved writer's
   5 s window elapses and `record_call_start`'s `BEGIN IMMEDIATE`/INSERT raises
   `OperationalError: database is locked` **before the audit row commits**.
4. That non-`SchwabApiError` propagates to the ladder's `except Exception` catch-all
   ([marketdata_ladder.py:456](../../../swing/integrations/schwab/marketdata_ladder.py) window /
   [:325](../../../swing/integrations/schwab/marketdata_ladder.py) quote), which logs **only the
   ticker** (no exception class, no message) → silent yfinance fallback, **no audit row**. This
   is why the operator had to hand-instrument the catch-all to discover the cause.

**Net:** the dominant lever is **`busy_timeout`** (give the serialized writers room to drain),
not "enable WAL" (already enabled). WAL-enable is demoted to *defense-in-depth* (for fresh /
test / never-migrated DBs). The symptom, the #23 amplifier, and the banked-item lineage are all
preserved; only the mechanism and the dominant lever are corrected.

### §2.4 Two contended consumer paths — they have DIFFERENT deadline regimes (Codex R1 major #3)

The two market-data consumer surfaces behave differently under a long busy_timeout, and the fix
must respect that:

- **OHLCV / bars path (`OhlcvCache.get_or_fetch`, ohlcv_cache.py:175).** **Synchronous, NO caller
  deadline** (docstring §"Concurrency: synchronous"). The worker simply waits for the lock and
  succeeds. This is the path the chart / detector / **pattern-observe** steps use — i.e. **exactly
  what #23 widened** (aplus→aplus+watch ⇒ the observe pool fetches OHLCV per detection). A longer
  `busy_timeout` is **safe and fully effective** here: the worker waits, the lock drains, the
  fetch succeeds, no premature abandonment. **This is the #23-amplified bulk of the degrade.**
- **Quote path (`PriceCache.get_many`, price_cache.py:369).** Bounded by a **6 s caller deadline**
  (`price_fetch_deadline_seconds`, config.py:380). If a worker waits on the SQLite lock longer
  than the remaining deadline, **the caller abandons it and records a yfinance fallback anyway**,
  even though the DB op may later succeed in the background. So a `busy_timeout` *larger than the
  caller deadline cannot rescue this path* — it only changes whether the late write eventually
  lands. The quote path is the **minority** surface (open-trade-ticker warm only, not widened by
  #23), but it bounds how much the busy_timeout bump alone can promise.

**Consequence for the design:** the busy_timeout bump **fixes the OHLCV path outright** (the
#23-amplified bulk) and **reduces but cannot fully guarantee** the quote path within its 6 s
ceiling. The honest goal (revised G1) is therefore *path-specific*, and the observability fix is
upgraded to **log the actual lock-wait duration** so the first instrumented live run reveals the
true wait distribution and decides whether write-pressure reduction (OQ-C) is also required.

---

## §3 Goals / non-goals

**Goals**
- G1 (path-specific, Codex R1 major #3) — **Eliminate** `OperationalError: database is locked` on
  the **no-deadline OHLCV path** (`get_or_fetch` — the #23-amplified bulk of the degrade) so the
  detection/observe/chart pool no longer drops to yfinance. On the **6 s-deadline quote path**,
  **substantially reduce** the degrade and **instrument** it (G2') so a residual is measurable and
  the write-pressure-reduction decision (OQ-C) is data-driven, not guessed. (We deliberately do
  NOT claim "eliminate" for the quote path within its 6 s ceiling.)
- G2 — Make the failure mode **observable**: the ladder catch-alls must log the exception
  class + message (redaction-safe) so any future opaque fallback is never silent again.
- G2' — **Lock-wait visibility:** record the SQLite lock-wait duration + the configured
  `busy_timeout` so a slow-drain (timeout-bump-sufficed) is distinguishable from a long-held-lock
  (write-pressure-reduction-needed) condition on the first live run (Codex R1 minor #2).
- G3 — A **discriminating** concurrency regression test that proves the contention pre-fix and
  green post-fix, exercising the production `connect()` wiring.
- G4 — Preserve every invariant in §8 (NO schema change; backup integrity; DB-outside-Drive;
  the data-integrity arc's barriers).

**Non-goals**
- Not a redesign of the audit-write transaction model (BEGIN IMMEDIATE stays).
- Not a rework of the executor / fan-out width.
- Not the OhlcvBar-invariant bad-bar issue (§9).
- No schema/migration (runtime PRAGMA only).

---

## §4 Proposed design — Approach A (centralized connection-pragma helper)

### §4.1 Approaches considered

- **A (RECOMMENDED):** A centralized low-level opener that applies `busy_timeout` (the operative
  lever) to **every** swing.db connection, routed through ALL contendable swing.db open sites (not
  just `connect()`); WAL stays where it already is (`ensure_schema`), **NOT reaffirmed on the hot
  path**; fold the ladder observability + lock-wait logging; add a production-path concurrency
  regression test.
- **B (REJECTED):** The brief's literal "enable WAL in `connect()`." Per §2.2 this is a **no-op
  on the already-WAL live DB**, does not fix the live problem, AND adds hot-path risk (R1 major
  #1). Rejected as a false fix.
- **C (CONDITIONAL — decide after the instrumented first run; Codex R1 major #3):** WAL +
  busy_timeout **+ write-pressure reduction** (a shared/serialized audit connection, or batching
  `record_call_start`/`record_call_finish`). Each audit write is a sub-millisecond INSERT/UPDATE,
  so on the no-deadline OHLCV path the busy_timeout bump should suffice. But on the 6 s-deadline
  quote path, if the G2' lock-wait telemetry from the first live run shows waits approaching the
  deadline (long-held lock, not mere starvation), write-pressure reduction becomes **necessary,
  not optional**. **V1 ships A + the telemetry; OQ-C decides whether C is pulled forward.**

### §4.2 The centralized low-level opener (revised per Codex R1 majors #1, #2, #5)

Introduce ONE opener in [`swing/data/db.py`](../../../swing/data/db.py) that every swing.db open
routes through. Because it is imported by other modules (web routes, cli, backup), it is a
**public** helper with a documented contract (Codex R2 minor #1 — not a leading-underscore
private). **Plumbing model (resolves R1 major #2 — no `cfg` in `db.py`, no import cycle, no
`connect()` signature blast radius):** a module-level default constant + keyword override; callers
with `cfg` may pass the tuned value, callers without get the default.

```
DEFAULT_BUSY_TIMEOUT_MS = 30000   # module-level; see OQ-A for value derivation

def open_connection(db_path_or_uri, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
                    reaffirm_wal: bool = False, uri: bool = False):
    """Public swing.db opener. Applies, in THIS order:
      1. busy_timeout  : FIRST — so any subsequent lock acquisition (incl. a
                         WAL reaffirm, BEGIN IMMEDIATE) is covered by the handler.
      2. foreign_keys=ON : existing invariant, unchanged.
      3. journal_mode=WAL: ONLY when reaffirm_wal=True (ensure_schema path).
                           NOT on the hot connect() path — the live DB is already
                           WAL (persistent), reaffirming it per-open is needless
                           overhead and a needless lock point (R1 major #1).
    `uri=True` forwards to sqlite3.connect(..., uri=True) so a caller can pass a
    `file:...?mode=rw` URI and KEEP fail-closed semantics (R2 major #1).
    busy_timeout is per-connection, NOT persistent (unlike WAL), so it MUST be
    set on EVERY connection — applying it once is insufficient.
    """
```

**Backup fail-closed preserved (R2 major #1).** `do_backup` opens the *source* with a
`file:...?mode=rw` URI (backup.py:66–67) **specifically so a missing DB is NOT silently created**
(the default `rwc` would fabricate empty garbage). The opener MUST preserve this: the backup
source either calls `open_connection(src_uri, uri=True, busy_timeout_ms=...)` (mode=rw retained)
OR keeps its existing `sqlite3.connect(src_uri, uri=True)` and simply adds a `PRAGMA busy_timeout`
after open. Either way **fail-closed `mode=rw` is non-negotiable** — the busy_timeout is additive,
not a replacement for the open semantics.

**Explicit raw-open inventory is a writing-plans deliverable (R2 major #2).** "All swing.db opens"
is only enforceable with a complete classified list. Writing-plans MUST produce a `grep`-derived
inventory of every `sqlite3.connect` in `swing/` and classify each as: (a) **live swing.db** →
route through `open_connection` (busy_timeout); (b) **backup DESTINATION** (a fresh file, e.g.
db.py:320/453/… `dest_conn`) → leave (busy_timeout irrelevant on a private fresh file); (c)
**backup SOURCE** (db.py:318/451/… `src_conn`, backup.py:67) → add busy_timeout, preserve open
semantics; (d) **probe / create** (cli.py friendly-error probes) → case-by-case; (e) **temp DB**
(auth.py:1665) → leave; (f) **separate tokens DB** (auth.py:729/2327, cli_schwab.py:495) → leave.
The §5 table is the starting set; the inventory makes it exhaustive.

**Ordering is load-bearing (R1 major #1):** set `busy_timeout` **before** any operation that can
take a lock. SQLite's busy handler, once installed, also covers the journal-mode pragma and
`BEGIN IMMEDIATE`. So even in `ensure_schema` (the only WAL-reaffirm site) a concurrent writer
holding the lock won't make the WAL pragma raise immediately — it waits under the handler.

**WAL is NOT reaffirmed on the hot path.** `connect()` calls `open_connection(..., reaffirm_wal=False)`.
Rationale: `connect()` raises on any non-current DB (db.py:1155–1167), so it only ever opens a DB
that already went through `ensure_schema` → already WAL persistently. Reaffirming WAL on every one
of the ≤16 concurrent hot-path opens buys nothing and adds a lock point. `ensure_schema` keeps
`reaffirm_wal=True` (covers a genuinely fresh DB). A no-arg `PRAGMA journal_mode` *read* as a
"is-it-really-WAL" guard is an **optional diagnostic only** (Codex R2 minor #2 — do NOT treat it
as a hot-path invariant or claim it is provably lock-free against an active writer); BANK / OQ-B
sub-decision.

**Call-site routing (R1 major #5 — make "centralized" true).** Every **swing.db** open that can
run concurrently with the nightly pipeline routes through `open_connection`:

- `connect()` (db.py:1159) and `ensure_schema()` (db.py:1128) — core.
- The web-route / view-model / cli direct opens on `cfg.paths.db_path` — `web/routes/schwab.py`,
  `web/routes/reconcile.py` (incl. the fresh-read at :437), `web/routes/account.py`,
  `web/routes/config.py`, `web/routes/metrics.py`, `web/routes/watchlist.py`,
  `web/view_models/schwab.py`, `web/app.py:389`, and the `cli.py` swing.db opens. These retain the
  5 s default today and **can** contend with the pipeline (operator browsing while the nightly run
  is active) — route them through `open_connection` so the busy_timeout is uniform.
- **Backup source open** (`backup.py:67`, the migration pre-backup at db.py:304+) — apply
  busy_timeout to the *source* connection (hygiene vs a live writer); the online backup API stays
  WAL-safe and unchanged.

**Explicitly OUT (different database file — cannot contend with swing.db):** the Schwab **tokens**
DB opens (`auth.py:729/2327`, `cli_schwab.py:495`) target `~/swing-data/schwab-tokens.{env}.db`,
a *separate* file with its own `timeout=1.0`. They do not touch swing.db and are left unchanged.

The exact per-call-site adoption list is finalized in writing-plans; the principle is: **all
swing.db opens, one opener, uniform busy_timeout.**

### §4.3 Observability fold-in (G2)

In **both** ladder catch-alls — `fetch_window_via_ladder`
([marketdata_ladder.py:456](../../../swing/integrations/schwab/marketdata_ladder.py)) and
`fetch_quote_via_ladder` ([:325](../../../swing/integrations/schwab/marketdata_ladder.py)) —
bind the exception and log its **class + message**:

- `except Exception as exc:` → `log.warning("... %s: %s", type(exc).__name__, exc)` (plus the
  ticker already present).
- **Redaction-safe:** log the **message string only** via the existing `setLogRecordFactory`
  content-redaction wrapper. **Do NOT use `exc_info=True`** — traceback frames can carry
  un-redacted locals/args that bypass the message-level redaction factory (CLAUDE.md Schwab
  log-redaction discipline).
- Remove the `# pragma: no cover` on these arms (they are now exercised by the regression test).

**Lock-wait telemetry (G2', Codex R1 minor #2).** Logging only the final class+message cannot
distinguish "the busy_timeout bump fixed it" from "a residual slow-drain is still occurring." Add
lightweight wait visibility so the first live run is self-diagnosing:

- In the audit-service write path (`record_call_start` / `record_call_finish`,
  audit_service.py:104/151), measure the wall-clock of the `BEGIN IMMEDIATE` acquisition and store
  the duration **locally**. **Do the logging AFTER the lock is released (post commit/rollback), NOT
  while holding the writer lock (Codex R2 major #3)** — emitting a WARNING inside the critical
  section would extend the exact contention window we are fixing (logging I/O can be slow). Emit
  when the stored duration exceeds a threshold (e.g. ≥ 1 s, well under the 30 s budget), with the
  elapsed wait + the configured `busy_timeout`.
- **Also log FAILED acquisitions, not only slow successful ones (R2 major #3):** when the
  `BEGIN IMMEDIATE` itself raises `OperationalError` (busy_timeout exhausted), log the elapsed wait
  + busy_timeout on the way out (in the `except`/rollback path, after releasing). The failure case
  is the most diagnostic of all.
- Keep it cheap and redaction-irrelevant (durations + integers, no secrets). Exact threshold +
  placement (wrap vs. a small timed-BEGIN helper) finalized in writing-plans.
- **Interpretation caveat (R2 minor #3):** the telemetry shows *that* an audit write waited, not
  *which* writer held the lock. The blocker may be a lease-fenced pipeline writer (candidates /
  archive / evaluate), not audit pressure. Writing-plans should consider whether the dominant
  non-audit pipeline writers also warrant the same timed-acquisition WARNING so the first live run
  localizes the true contender, not only the audit victim.

This is the fix the opaque banked T-C.1 issue always needed; it is what made the live root cause
discoverable only by hand-instrumentation.

### §4.4 Data flow (unchanged except pragmas + logging)

```
executor worker (×≤8 OHLCV + ≤8 quote)
  → connect(db_path)            # NOW: busy_timeout=30s + FK=ON (NO WAL reaffirm — already WAL)
    → fetch_{quote,window}_via_ladder
      → get_{quotes_batch,price_history}
        → record_call_start   (BEGIN IMMEDIATE INSERT)   ← serialized; waits ≤busy_timeout, drains
                                                            ← if wait ≥1s: WARNING(wait, busy_timeout)  [G2']
        → <HTTP>
        → record_call_finish  (BEGIN IMMEDIATE UPDATE)   ← serialized; waits ≤busy_timeout, drains
      ← on ANY exception: catch-all logs CLASS+MESSAGE (redaction-safe, no exc_info) → yfinance fallback
  → conn.close()

OHLCV path (get_or_fetch): NO caller deadline → long busy_timeout fully effective (the #23 bulk).
Quote path (get_many):     6s caller deadline → busy_timeout reduces, telemetry decides OQ-C.
```

---

## §5 Surfaces & blast radius decisions (dispatch brief §3)

The DB connection is touched by many call sites; a naive change has wide blast radius. Decisions:

| Surface | Finding (grounded) | Decision |
|---|---|---|
| **`connect()`** db.py:1159 | No busy_timeout / no `timeout=`; the contended pipeline path. | **IN SCOPE — `open_connection(reaffirm_wal=False)`.** busy_timeout only; NO hot-path WAL reaffirm (R1 major #1). The live fix. |
| **`ensure_schema()`** db.py:1128 | Already sets WAL; no busy_timeout. | **IN SCOPE — `open_connection(reaffirm_wal=True)`** (busy_timeout FIRST, then WAL — the only WAL site). |
| **Direct `sqlite3.connect(cfg.paths.db_path)` in web routes / cli / `app.py:389` / `view_models`** | Bypass `connect()`; retain Python's 5 s default; inherit persistent WAL. **CAN contend** with the nightly pipeline (operator browsing during the run) — R1 major #5. | **IN SCOPE (V1) — route through `open_connection`.** Uniform busy_timeout across all swing.db opens; this is what makes "centralized" true. Exact list finalized in writing-plans. |
| **Schwab tokens-DB opens** (`auth.py:729/2327`, `cli_schwab.py:495`) | Target a **separate** file `schwab-tokens.{env}.db`, own `timeout=1.0`. | **OUT — different file, cannot contend with swing.db.** Unchanged. |
| **Migration runner** (`run_migrations`, `executescript`, `foreign_keys=OFF`) | Runs single-connection under `ensure_schema`. WAL + `executescript` interplay: `executescript` issues implicit COMMIT — already handled by the explicit `BEGIN`/COMMIT discipline (CLAUDE.md #9). WAL is orthogonal. | **No change** beyond the `ensure_schema` helper. Confirm migration tests stay green. |
| **Backup (weekly + pre-migration)** backup.py:67 / db.py:304+ | Uses WAL-safe online `Connection.backup()` API + `PRAGMA integrity_check`; already WAL-aware. | **Backup API unchanged** (stays WAL-safe). **Apply busy_timeout to the *source* open** so a weekly backup taken mid-pipeline doesn't fail fast on the 5 s default (R1 major #5 hygiene). |
| **Migration backup-gate** (`pre_version == target-1`, strict equality) | Independent of journal mode. | **Untouched / preserved.** |
| **WAL sidecars (`-wal`/`-shm`)** | Live beside `~/swing-data/swing.db`, **OUTSIDE** the Drive dir. No code path puts a WAL DB on the Drive (DB-location invariant). | **Safe.** Confirm no test/dev DB lands on the Drive. |
| **Test suite (~7175 tests)** | `tmp_path` DBs created via `ensure_schema` get WAL already; WAL produces `-wal`/`-shm` sidecars under `tmp_path` (auto-cleaned with the tmp dir). Need to confirm no test asserts `journal_mode` is a rollback mode or breaks on sidecars. | **Audit required** in writing-plans: grep tests for `journal_mode` / `PRAGMA` assertions; confirm tmp cleanup tolerates sidecars. Expected impact: none (WAL already in effect for `ensure_schema`-built test DBs today). |
| **WAL checkpoint strategy** | Default auto-checkpoint (1000 pages / ~4 MB at 4 KB pages). `-wal` growth bounded by auto-checkpoint; clean close checkpoints + removes sidecars. | **Keep the SQLite default auto-checkpoint** for V1 (no explicit `wal_checkpoint`). Document; revisit only if `-wal` growth is observed. |
| **`.gitignore`** | Live DB is outside the repo. Any in-repo dev/test DB would spawn `*.db-wal`/`*.db-shm`. | **OPTIONAL hygiene, NON-blocking** (R1 minor #3 — orthogonal to the degrade). Add `*.db-wal`/`*.db-shm`/`*.db-journal` patterns if convenient; not a correctness step. |

---

## §6 Test strategy (discriminating; `feedback_regression_test_arithmetic`)

The regression must **distinguish** pre-fix from post-fix. Two layers:

1. **Deterministic config assertion (always reliable).**
   Open a DB via the production `connect()` and assert:
   - `PRAGMA journal_mode` → `'wal'`, and
   - `PRAGMA busy_timeout` → the configured value (e.g. `30000`).
   Pre-fix this fails; post-fix it passes.
   **Arithmetic check (`feedback_regression_test_arithmetic`):** CPython's
   `sqlite3.connect(timeout=5.0)` calls `sqlite3_busy_timeout(db, 5000)` under the hood, so a
   pre-fix `connect()` reports `PRAGMA busy_timeout` → **`5000`** (the Python default surfaced),
   NOT `0`. The assertion therefore flips **`5000` → `30000`** — assert `== 30000` (which `5000`
   fails) so it genuinely distinguishes pre/post. `PRAGMA journal_mode` reads `'wal'` BOTH pre-
   and post-fix (WAL is already persistent), so the journal_mode assertion is a regression-pin,
   **not** the discriminator; **busy_timeout is the discriminator.**

2. **Behavioral concurrency reproduction (lower-level).**
   - **Pre-fix demonstrator:** N (≥8) threads, each opening a connection with a *deliberately
     tiny* busy timeout (e.g. `sqlite3.connect(db, timeout=0)` or `PRAGMA busy_timeout=1`) and
     concurrently issuing `BEGIN IMMEDIATE` audit-row INSERTs against a shared on-disk DB →
     assert at least one raises `OperationalError: database is locked`. (Proves the contention is
     real and that an inadequate busy_timeout is the trigger.)
   - **Post-fix assertion:** N threads, each via the production `connect()` (now busy_timeout=30 s)
     concurrently calling `record_call_start` → assert **all N rows land** and **no
     `OperationalError`**.
   - **Determinism caveat:** with sub-ms writes, a *long* busy_timeout drains the writers far
     under budget so the post-fix path is reliably green; the pre-fix FAILURE is reliable only
     with a near-zero busy_timeout (hence the tiny-timeout demonstrator, not wall-clock
     starvation, which is machine-dependent).

3. **Production-path stress test (Codex R1 major #4 — the one that proves the LIVE fix).**
   Layer 2 only proves a bare INSERT can lock; it does NOT exercise the real
   start-write → HTTP → finish-write sequence (marketdata.py:551 / :711) under concurrency. Add a
   test that drives the **ladder wrapper itself** (`fetch_window_via_ladder` /
   `get_price_history`) across ≥8 threads with a **mocked Schwab client that injects latency**
   between the start and finish writes (so each worker holds the start/finish window open like the
   real HTTP call does), **plus** one or more *other* concurrent `BEGIN IMMEDIATE` writers
   (simulating candidates/archive/evaluate writers), against a shared on-disk DB opened via the
   production opener. Post-fix (30 s busy_timeout) → all Schwab attempts complete, audit rows land,
   no degrade.
   - **Split the pre-fix assertion by failure point (Codex R2 major #4 — the "no audit row"
     assumption is not universal).** `record_call_start` **commits before** the HTTP call
     (marketdata.py:551), so the audit-row state depends on WHERE the lock fails:
     - **forced-start-lock case** (the contended write is `record_call_start`): the INSERT never
       commits → assert **no audit row** + yfinance fallback.
     - **forced-finish-lock case** (start already committed, the contended write is
       `record_call_finish`): assert an **in-flight audit row remains** (status still in-flight,
       never finalized) + yfinance fallback. This is the more realistic invisibility mode and the
       "no row" assertion would be WRONG here.
   - **Quote-path deadline variant:** run the same stress under the `get_many` 6 s caller deadline
     (price_cache.py:369) with injected lock-hold latency to characterize where the busy_timeout
     bump stops helping (feeds the OQ-C decision). This need not be a hard pass/fail gate — it can
     assert the G2' wait-telemetry WARNING fires when a wait approaches the deadline.

4. **Observability test.** Force the ladder's Schwab path to raise a generic `Exception`
   (e.g. monkeypatch `get_price_history` to raise `OperationalError("database is locked")`) and
   assert the WARNING log record contains the **class name and message** and that no traceback
   (`exc_info`) is emitted. A redaction sentinel test: plant a fake-secret in the message and
   confirm the `setLogRecordFactory` wrapper redacts it. Plus a G2' test: a slow `BEGIN IMMEDIATE`
   acquisition emits the wait-duration WARNING.

5. **Backup-under-WAL test.** `do_backup` against a WAL DB with an open writer connection →
   assert the backup file passes `PRAGMA integrity_check` (guards the §5 backup decision).

---

## §7 Open questions for operator triage

> Surfaced for asynchronous operator triage (the operator dispatched this brainstorm and is not
> interactively present). Resolve operator-paired before / during writing-plans.

- **OQ-0 (NEW — the headline; highest priority).** Confirm **Refinement R1**: the live DB is
  already in WAL mode, so the operative lever is **`busy_timeout`**, with WAL-enable as
  defense-in-depth (not the live fix). The brief's "enable WAL" framing is superseded by
  evidence. **Recommendation: accept R1.** (If the operator wants independent confirmation, a
  one-line `PRAGMA journal_mode` read on the live DB `mode=ro` reproduces the header finding.)
- **OQ-A (refined per R1 major #3).** `busy_timeout` value. **Two regimes:** the OHLCV path has
  no deadline so a generous value is safe — recommend **30000 ms**. But the value should not be
  set blindly above the quote path's 6 s caller deadline expecting it to rescue that path (it
  cannot — §2.4). Operator decision: a single uniform `busy_timeout` (recommend 30000 ms, simple,
  optimal for the #23-amplified OHLCV bulk) vs a per-surface value. Plumbing: module-level
  `DEFAULT_BUSY_TIMEOUT_MS` constant + keyword override (recommended — no `cfg` in `db.py`, no
  import cycle; a `cfg.web.db_busy_timeout_ms` knob can feed the override at the pipeline callsite
  if the operator wants runtime tuning).
- **OQ-B (refined per R1 major #5).** Centralization scope. **Recommend V1 = route ALL swing.db
  opens through `open_connection`** (connect, ensure_schema, the web-route/cli/view-model direct
  opens, the backup source), since the web opens CAN contend with the nightly run. The
  schwab-tokens.db opens are a separate file → excluded. Sub-decision: also add an OPTIONAL
  `PRAGMA journal_mode` read-guard in `connect()` (a diagnostic, not a hot-path invariant — see
  §4.2 / R2 minor #2)? (recommend optional.)
- **OQ-C (ELEVATED per R1 major #3 — no longer a pure "bank").** Is busy_timeout sufficient, or
  is write-pressure reduction also needed? **V1 ships busy_timeout + the G2' lock-wait telemetry;
  the FIRST instrumented live run decides:** if waits are short-but-starved → busy_timeout
  sufficed (close C). If waits approach the deadline on the quote path (long-held lock) →
  write-pressure reduction (shared/serialized audit connection, or batching start/finish) becomes
  **necessary** and is pulled forward as the immediate follow-on. This is a data-driven gate, not
  a guess.
- **OQ-D.** Fold the catch-all observability logging into THIS arc — **recommend yes** (it is the
  fix that made the live root cause discoverable; cheap; in the same files).
- **OQ-E.** The *separate* OhlcvBar-invariant bad-bar issue (~2–4/run regular-session bars from
  Schwab; the data-integrity arc already makes these a clean typed→yfinance fallback): **bank as
  accepted (recommended)** vs in-scope. Distinct root cause; recommend BANK.

---

## §8 Locks / invariants preserved

- **NO schema change** — runtime PRAGMA only; **schema v24 holds.**
- **DB-outside-Drive** (hard invariant) — WAL sidecars live beside `~/swing-data/swing.db`,
  outside the Drive dir. No code path puts a WAL DB on the Drive.
- **Backup integrity** + the **migration backup-gate** (`pre_version == target-1`, strict
  equality) preserved; online backup API is WAL-safe.
- The **data-integrity arc's** write-barrier / date-only lock-guard / typed
  `SchwabBarConsistencyError` / uniform topbar remain intact — this arc is orthogonal
  (connection config, not market-data logic).
- **L3 append-only observation lock** untouched.
- **L2 LOCK** (schwabdev endpoint baseline) untouched — no Schwab REST surface change.
- Audit-service single-transaction discipline (`BEGIN IMMEDIATE` ownership, reject caller-held
  tx) **unchanged**.
- ZERO `Co-Authored-By`; conventional commits; no `--no-verify`.

---

## §9 Out of scope

- The **OhlcvBar-invariant bad-bar issue** (OQ-E; likely banked — distinct root cause).
- The data-integrity arc's open items (Gate 4 cassette; the arc close).
- Issue #3 metrics fix; Schwab Phase B/C.
- Any schema/migration; any executor/fan-out redesign.
- Write-pressure reduction / audit-write txn-model rework (Approach C) — **conditional** follow-on,
  pulled forward only if the G2' first-live-run telemetry shows it is needed (OQ-C).

---

## §10 Writing-plans readiness

This spec is execution-ready for `copowers:writing-plans` once OQ-0 / OQ-A / OQ-B / OQ-C are
confirmed (OQ-D / OQ-E carry recommendations that can stand as defaults). The implementation is
small and well-bounded:

1. `swing/data/db.py` — add the public `open_connection(db_path_or_uri, *,
   busy_timeout_ms=DEFAULT_BUSY_TIMEOUT_MS, reaffirm_wal=False, uri=False)` opener + the
   `DEFAULT_BUSY_TIMEOUT_MS = 30000` constant; busy_timeout applied FIRST; `uri=True` preserves
   `file:...?mode=rw` fail-closed semantics; `connect()` → `reaffirm_wal=False`; `ensure_schema()`
   → `reaffirm_wal=True`. **No `cfg` import in `db.py`** (module constant + keyword override only).
2. **Produce the classified raw-open inventory (R2 major #2)** then route the **live-swing.db**
   direct opens (web routes / view-models / cli / `app.py:389`) through `open_connection`; add
   `PRAGMA busy_timeout` to the backup **source** open while preserving its `mode=rw` URI (R2
   major #1); leave backup destinations / temp DBs / tokens DB unchanged. Optionally add a
   `cfg.web.db_busy_timeout_ms` knob feeding the keyword override at the pipeline callsite.
3. `swing/integrations/schwab/marketdata_ladder.py` — bind `exc` + log class+message
   (redaction-safe, no `exc_info`) in both catch-alls; drop the `# pragma: no cover`.
4. `swing/integrations/schwab/audit_service.py` — G2' timed `BEGIN IMMEDIATE`; **log AFTER lock
   release** (never inside the critical section); log slow successes AND failed acquisitions.
5. Tests — the five layers in §6 (config assertion, concurrency reproduction, **production-path
   stress split by failure point**, observability + redaction + G2' wait, backup-under-WAL); plus
   the §5 test-audit grep (`journal_mode`/`PRAGMA` assertions; sidecar cleanup).
6. `.gitignore` — OPTIONAL `*.db-wal` / `*.db-shm` / `*.db-journal` (non-blocking).

No new files, no schema, no migration. The expected test-suite impact is **small/none** (WAL is
already in effect for `ensure_schema`-built DBs; the change adds an explicit busy_timeout + richer
logging + the opener-routing), pending the §5 test-audit grep in writing-plans.

---

*End of spec. The headline refinement (R1, §2.2): WAL is already on — `busy_timeout` is the fix.*
