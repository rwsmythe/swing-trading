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
- §2 **Grounded root cause** — incl. **Refinement R1 (the headline finding): WAL is ALREADY on; `busy_timeout` is the operative lever**
- §3 Goals / non-goals
- §4 Proposed design (Approach A) — the centralized pragma helper, observability fold-in, regression test
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

**Therefore `connect()`'s lack of an explicit `PRAGMA journal_mode=WAL` does NOT put its
connections in rollback-journal mode** — they inherit the persistent WAL mode from the file
header. Adding `PRAGMA journal_mode=WAL` to `connect()` would be a **no-op on the live DB** and
would **not** fix the operator's problem.

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

---

## §3 Goals / non-goals

**Goals**
- G1 — Eliminate `OperationalError: database is locked` on the concurrent pipeline fetch path so
  Schwab market-data succeeds for the full open-trade / detection pool instead of degrading
  ~13–22 tickers/run to yfinance.
- G2 — Make the failure mode **observable**: the ladder catch-alls must log the exception
  class + message (redaction-safe) so any future opaque fallback is never silent again.
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

- **A (RECOMMENDED):** Add one centralized helper that applies the connection pragmas
  (`journal_mode=WAL` + `busy_timeout=<N>`) and call it from the canonical connection openers
  (`connect()` + `ensure_schema()`); fold the ladder observability fix; add the regression test.
- **B (REJECTED):** The brief's literal "enable WAL in `connect()`." Per §2.2 this is a **no-op
  on the already-WAL live DB** and does not fix the live problem. Rejected as a false fix.
- **C (REJECTED for V1):** WAL + busy_timeout **+ write-pressure reduction** (a shared/serialized
  audit connection, or batching `record_call_start`/`record_call_finish`). Over-engineered for
  V1: each audit write is a sub-millisecond INSERT/UPDATE, so 16 serialized writers drain in
  well under a 30 s budget. Bank write-pressure reduction as a follow-on gated on the regression
  test or a live run still showing contention (see OQ-C).

### §4.2 The centralized pragma helper

Introduce a single module-level helper in [`swing/data/db.py`](../../../swing/data/db.py),
e.g.:

```
def _apply_connection_pragmas(conn) -> None:
    """Apply the standard app connection pragmas.
    - journal_mode=WAL  : defense-in-depth (no-op on an already-WAL DB; flips
                          fresh / test / never-migrated DBs). NOT the live fix.
    - busy_timeout=<N>  : THE operative lever — gives serialized WAL writers
                          room to drain under concurrent pipeline load.
    - foreign_keys=ON   : existing invariant, unchanged.
    """
```

- The `busy_timeout` value is configurable (default candidate **30000 ms** — see OQ-A); sourced
  from config so the operator can tune without a code change. **Design rule:** `busy_timeout`
  is **per-connection, NOT persistent** (unlike WAL), so it MUST be applied on *every*
  connection on the contended path — applying it once is insufficient.
- Call the helper from **`connect()`** (db.py:1159 — the contended pipeline path; THE live fix)
  and from **`ensure_schema()`** (db.py:1128 — already sets WAL; add busy_timeout for
  migration-time safety, harmless).
- Ordering note: `PRAGMA journal_mode=WAL` returns a row and must run **outside** a transaction;
  `connect()` opens in autocommit so this is satisfied. `busy_timeout` and `foreign_keys` are
  cheap autocommit pragmas. The helper runs immediately after `sqlite3.connect`, before the
  schema-version check.

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

This is the fix the opaque banked T-C.1 issue always needed; it is what made the live root cause
discoverable only by hand-instrumentation.

### §4.4 Data flow (unchanged except pragmas + logging)

```
executor worker (×≤16)
  → connect(db_path)            # NOW: WAL(no-op) + busy_timeout=30s + FK=ON
    → fetch_{quote,window}_via_ladder
      → get_{quotes_batch,price_history}
        → record_call_start   (BEGIN IMMEDIATE INSERT)   ← serialized; waits ≤30s, drains
        → <HTTP>
        → record_call_finish  (BEGIN IMMEDIATE UPDATE)   ← serialized; waits ≤30s, drains
      ← on ANY exception: catch-all logs class+message (redaction-safe) → yfinance fallback
  → conn.close()
```

---

## §5 Surfaces & blast radius decisions (dispatch brief §3)

The DB connection is touched by many call sites; a naive change has wide blast radius. Decisions:

| Surface | Finding (grounded) | Decision |
|---|---|---|
| **`connect()`** db.py:1159 | No busy_timeout / no `timeout=`; the contended pipeline path. | **IN SCOPE — apply helper.** The live fix. |
| **`ensure_schema()`** db.py:1128 | Already sets WAL; no busy_timeout. | **IN SCOPE — apply helper** (adds busy_timeout; WAL unchanged). |
| **Direct `sqlite3.connect` in web routes / cli / `app.py:389` / `view_models`** | Bypass `connect()`; get Python's 5 s default + inherit persistent WAL from header. Low per-request concurrency. | **BANK (OQ-B).** Not on the contended pipeline path. Recommend a follow-on hygiene pass routing them through a shared opener; not required for the live fix. |
| **Migration runner** (`run_migrations`, `executescript`, `foreign_keys=OFF`) | Runs single-connection under `ensure_schema`. WAL + `executescript` interplay: `executescript` issues implicit COMMIT — already handled by the explicit `BEGIN`/COMMIT discipline (CLAUDE.md #9). WAL is orthogonal. | **No change** beyond the `ensure_schema` helper. Confirm migration tests stay green. |
| **Backup (weekly + pre-migration)** backup.py / db.py:304+ | Uses WAL-safe online `Connection.backup()` API + `PRAGMA integrity_check`; already WAL-aware. | **No change.** Backups stay valid under WAL. (Optional: add busy_timeout to the backup *source* open as hygiene vs a live writer — BANK, OQ-B.) |
| **Migration backup-gate** (`pre_version == target-1`, strict equality) | Independent of journal mode. | **Untouched / preserved.** |
| **WAL sidecars (`-wal`/`-shm`)** | Live beside `~/swing-data/swing.db`, **OUTSIDE** the Drive dir. No code path puts a WAL DB on the Drive (DB-location invariant). | **Safe.** Confirm no test/dev DB lands on the Drive. |
| **Test suite (~7175 tests)** | `tmp_path` DBs created via `ensure_schema` get WAL already; WAL produces `-wal`/`-shm` sidecars under `tmp_path` (auto-cleaned with the tmp dir). Need to confirm no test asserts `journal_mode` is a rollback mode or breaks on sidecars. | **Audit required** in writing-plans: grep tests for `journal_mode` / `PRAGMA` assertions; confirm tmp cleanup tolerates sidecars. Expected impact: none (WAL already in effect for `ensure_schema`-built test DBs today). |
| **WAL checkpoint strategy** | Default auto-checkpoint (1000 pages / ~4 MB at 4 KB pages). `-wal` growth bounded by auto-checkpoint; clean close checkpoints + removes sidecars. | **Keep the SQLite default auto-checkpoint** for V1 (no explicit `wal_checkpoint`). Document; revisit only if `-wal` growth is observed. |
| **`.gitignore`** | Live DB is outside the repo. Any in-repo dev/test DB would spawn `*.db-wal`/`*.db-shm`. | **Add `*.db-wal` / `*.db-shm` (and `-journal`) ignore patterns** as cheap insurance. |

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

2. **Behavioral concurrency reproduction.**
   - **Pre-fix demonstrator:** N (≥8) threads, each opening a connection with a *deliberately
     tiny* busy timeout (e.g. `sqlite3.connect(db, timeout=0)` or `PRAGMA busy_timeout=1`) and
     concurrently issuing `BEGIN IMMEDIATE` audit-row INSERTs against a shared on-disk DB →
     assert at least one raises `OperationalError: database is locked`. (Proves the contention is
     real and that an inadequate busy_timeout is the trigger.)
   - **Post-fix assertion:** N threads, each via the production `connect()` (now WAL + 30 s
     busy_timeout) concurrently calling `record_call_start` → assert **all N rows land** and
     **no `OperationalError`** is raised.
   - **Determinism caveat (document in the plan):** with sub-millisecond writes, a *long*
     busy_timeout drains 16 writers far under budget, so the post-fix path is reliably green; the
     pre-fix FAILURE is only reliable with a near-zero busy_timeout (hence the tiny-timeout
     demonstrator rather than relying on wall-clock starvation, which is machine-dependent).

3. **Observability test.** Force the ladder's Schwab path to raise a generic `Exception`
   (e.g. monkeypatch `get_price_history` to raise `OperationalError("database is locked")`) and
   assert the WARNING log record contains the **class name and message** and that no traceback
   (`exc_info`) is emitted. A redaction sentinel test: plant a fake-secret in the message and
   confirm the `setLogRecordFactory` wrapper redacts it.

4. **Backup-under-WAL test.** `do_backup` against a WAL DB with an open writer connection →
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
- **OQ-A.** `busy_timeout` value: **10 s vs 30 s** (recommend **30000 ms** — ample headroom for
  16 serialized sub-ms writers; the cost of a too-low value is the exact bug we're fixing).
  And: config-sourced (recommend yes, default 30000) vs hard-coded constant.
- **OQ-B.** Pragma scope: **`connect()` + `ensure_schema()` only (V1, recommended)** vs also the
  direct `sqlite3.connect` callsites (web routes / cli / `app.py:389` / backup source). Recommend
  V1 = the two canonical openers; bank the broader hygiene pass.
- **OQ-C.** **WAL + busy_timeout alone (V1, recommended)** vs also write-pressure reduction
  (shared/serialized audit connection) now. Recommend WAL+busy_timeout V1; bank write-pressure
  reduction, gated on the regression test / first live run still showing contention.
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
- Any schema/migration; any executor/fan-out redesign; any audit-write txn-model rework.
- Write-pressure reduction (Approach C) — banked follow-on per OQ-C.

---

## §10 Writing-plans readiness

This spec is execution-ready for `copowers:writing-plans` once OQ-0 / OQ-A / OQ-C are confirmed
(OQ-B / OQ-D / OQ-E carry recommendations that can stand as defaults). The implementation is
small and well-bounded:

1. `swing/data/db.py` — add `_apply_connection_pragmas` helper; call from `connect()` +
   `ensure_schema()`; config-sourced busy_timeout (default 30000 ms).
2. `swing/config.py` — add the `busy_timeout` knob (e.g. `db_busy_timeout_ms: int = 30000`).
3. `swing/integrations/schwab/marketdata_ladder.py` — bind `exc` + log class+message
   (redaction-safe, no `exc_info`) in both catch-alls; drop the `# pragma: no cover`.
4. Tests — the four layers in §6 (config assertion, concurrency reproduction, observability +
   redaction, backup-under-WAL).
5. `.gitignore` — `*.db-wal` / `*.db-shm` / `*.db-journal`.

No new files, no schema, no migration. The expected test-suite impact is **none** (WAL is already
in effect for `ensure_schema`-built DBs; the change adds an explicit busy_timeout + WAL
reaffirmation + richer logging), pending the §5 test-audit grep in writing-plans.

---

*End of spec. The headline refinement (R1, §2.2): WAL is already on — `busy_timeout` is the fix.*
