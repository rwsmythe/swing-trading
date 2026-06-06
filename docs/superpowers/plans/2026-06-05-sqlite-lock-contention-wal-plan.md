# SQLite Lock-Contention (busy_timeout + serialized audit writer) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate `sqlite3.OperationalError: database is locked` on the nightly market-data fetch path (the silent Schwab→yfinance degrade for ~13–22 tickers/run) by giving every swing.db connection a 30 s `busy_timeout` AND collapsing the ≤16 concurrent per-hook audit connections into ONE serialized audit-writer connection — while making the failure mode observable.

**Architecture:** A centralized low-level opener (`open_connection`) in `swing/data/db.py` applies `busy_timeout` FIRST to every swing.db connection; WAL is NOT reaffirmed on the hot path (the live DB is already WAL — persistent in the file header). Write-pressure is reduced in V1 (operator OQ-C override) via a process-wide **serialized audit-writer connection**: a single `sqlite3.Connection` (opened `check_same_thread=False`) guarded by a module-level lock, so the 16 pipeline fetch workers funnel their `record_call_start`/`record_call_finish` writes through one connection serialized by a cheap in-process lock instead of 16 connections contending on SQLite's single write lock. The two ladder catch-alls gain class+message logging (redaction-safe, no `exc_info`); the audit path gains lock-wait telemetry so the first live run is self-diagnosing.

**Tech Stack:** Python 3.14, stdlib `sqlite3` (WAL), `threading.Lock`, FastAPI/HTMX web layer, pytest (`-m "not slow"`, xdist), ruff. **NO schema change — schema v24 holds.** Runtime PRAGMA + connection plumbing + logging only.

---

## Background (STEP-0 grounded at HEAD `bedd8264`; re-ground every `file:line` before editing — discipline #2)

**R1 RE-CONFIRMED (live DB header, zero-connection read 2026-06-06):** `~/swing-data/swing.db` bytes[18,19] = `2,2` = **WAL**, page_size 4096. WAL is a *persistent* file property set once by `ensure_schema` (`swing/data/db.py:1132`). Therefore `connect()`'s lack of an explicit `PRAGMA journal_mode=WAL` does NOT put it in rollback-journal mode — and reaffirming WAL on the hot path buys nothing and adds a lock point. **`busy_timeout` is the operative lever, NOT WAL-enable.**

**The failure chain (spec §2.3):** `connect()` (`db.py:1159`) sets no `busy_timeout` → only Python's implicit `sqlite3.connect(timeout=5.0)` (≈ `busy_timeout=5000`) applies. Up to 16 concurrent hook connections (`cfg.web.max_concurrent_ohlcv_fetches=8` + `max_concurrent_price_fetches=8`, `config.py:381,386`) each issue **two** `BEGIN IMMEDIATE` write txns (`record_call_start` `audit_service.py:104` + `record_call_finish` `audit_service.py:151`). Under sustained #23-amplified pressure a starved writer's 5 s window elapses → `OperationalError: database is locked` raised *before* the audit row commits → propagates to the ladder `except Exception` catch-alls (`marketdata_ladder.py:325` quote, `:456` window) which log **only the ticker** → silent yfinance fallback, no audit trace.

**Two deadline regimes (spec §2.4):**
- **OHLCV/bars path** (`OhlcvCache.get_or_fetch`, `ohlcv_cache.py:175`; "Concurrency: synchronous", `:209`) — **NO caller deadline.** A 30 s `busy_timeout` fully fixes it. This is the #23-amplified bulk.
- **Quote path** (`PriceCache.get_many`, `price_cache.py:323`; `as_completed(..., timeout=deadline_seconds)`, `:369`) — bounded by a **6 s caller deadline** (`price_fetch_deadline_seconds=6`, `config.py:380`). A `busy_timeout` larger than 6 s cannot rescue it; the write-pressure reduction (OQ-C) is what protects it.

**KEY grounding for OQ-C (the design-bearing decision):** in the market-data path the per-hook `conn` is used **EXCLUSIVELY for audit writes**. `_call_endpoint` (`marketdata.py:551`–`:719`) calls `conn` only via `audit_service.record_call_start`/`record_call_finish`; the HTTP call (`client_method()`) and signature hash (`_compute_signature_hash(payload, endpoint=...)`) do NOT touch `conn`; the ladder's `_persist_window_to_archive` uses `cache_dir` (parquet), not `conn`. So the per-hook connection can be replaced by ONE shared serialized audit connection with zero disturbance to non-audit logic.

### Operator OQ resolutions (LOCKed 2026-06-06 — propagated, do NOT re-open)
- **OQ-0 ACCEPT R1.** WAL already on; `busy_timeout` is the lever. WAL-enable is defense-in-depth (kept only in `ensure_schema`). Do NOT reaffirm WAL on the hot `connect()` path.
- **OQ-A:** `DEFAULT_BUSY_TIMEOUT_MS = 30000` module const + keyword override + a `cfg.web.db_busy_timeout_ms` knob feeding the override at the pipeline/web callsites — **no `cfg` import in `db.py`** (module const + keyword only). `busy_timeout` set FIRST, before any other pragma / lock op.
- **OQ-B:** Route ALL swing.db opens through `open_connection`; backup SOURCE keeps fail-closed `mode=rw`; tokens.db excluded (separate file). The classified raw-open inventory is below.
- **OQ-C (DESIGN-BEARING — IN V1):** write-pressure reduction ships in V1 via a **serialized shared audit-writer connection** (selected mechanism + rationale below). Preserves the single-tx discipline, the in-flight-row visibility contract, and thread-safety.
- **OQ-D:** fold both ladder catch-all observability logs (class+message; redaction-safe; NOT `exc_info`).
- **OQ-E:** the OhlcvBar bad-bar issue is OUT (its own arc) — not addressed, not banked here.

### Raw-open inventory (OQ-B deliverable — `grep -rn "sqlite3.connect" swing/`, classified)

| File:line | Variable / context | Class | Action |
|---|---|---|---|
| `swing/data/db.py:1159` | `connect()` | **(a) live swing.db** | Route via `open_connection(reaffirm_wal=False)`; add `busy_timeout_ms` keyword. |
| `swing/data/db.py:1131` | `ensure_schema()` | **(a) live swing.db (WAL site)** | Route via `open_connection(reaffirm_wal=True)`. |
| `swing/data/db.py:318,451,475,500,525,552,579,602,630` | `src_conn` (pre-migration backup helpers `_create_pre_*_migration_backup`) | **(c) backup SOURCE** | Route src via `open_connection(src_path, busy_timeout_ms=DEFAULT_BUSY_TIMEOUT_MS)`. |
| `swing/data/db.py:320,453,477,502,527,554,581,604,632` | `dest_conn` (same helpers) | **(b) backup DEST (fresh file)** | Leave unchanged. |
| `swing/data/db.py:352` | `conn = connect(backup_path)` (integrity read of a backup) | **(d) backup read-back** | Leave unchanged. |
| `swing/data/backup.py:67` | `src` (`file:...?mode=rw` URI) | **(c) backup SOURCE** | `open_connection(src_uri, uri=True, busy_timeout_ms=DEFAULT_BUSY_TIMEOUT_MS)` — **preserve `mode=rw` fail-closed**. |
| `swing/data/backup.py:79` | `dst` (temp backup dest) | **(b) backup DEST** | Leave unchanged. |
| `swing/cli.py:149` | `_apply_toml_divergence_check` (live read at startup) | **(a) live swing.db** | Route via `open_connection`. |
| `swing/cli.py:211` / `:212` | `src` / `dst` (`db-migrate` backup) | **(c) SOURCE** / **(b) DEST** | src → `open_connection`; dst leave. |
| `swing/cli.py:227` | `_probe` (version snoop during `db-migrate`) | **(d) live probe** | Route via `open_connection` (low concurrency; uniformity). |
| `swing/cli.py:5160,5201` | `diagnose ... --db` (operator-supplied path) | **(a) live swing.db (arg)** | Route via `open_connection` (existence pre-guarded by `_validate_diagnose_db_path`). |
| `swing/cli_schwab.py:495` | tokens DB (`ro_uri`, `timeout=1.0`) | **(f) tokens DB** | **OUT** — separate file. |
| `swing/integrations/schwab/auth.py:729,2327` | tokens DB (`ro_uri`, `timeout=1.0`) | **(f) tokens DB** | **OUT** — separate file. |
| `swing/integrations/schwab/auth.py:1665` | temp DB | **(e) temp DB** | **OUT** — private temp. |
| `swing/web/app.py:389` | live read | **(a) live swing.db** | Route via `open_connection`. |
| `swing/web/routes/account.py:89,120,149` | live | **(a)** | Route via `open_connection`. |
| `swing/web/routes/config.py:71,141,224` | live (+ cascade conns) | **(a)** | Route via `open_connection`. |
| `swing/web/routes/metrics.py:54,249` | live | **(a)** | Route via `open_connection`. |
| `swing/web/routes/reconcile.py:147,437,513` | live (incl. fresh-read `:437`) | **(a)** | Route via `open_connection`. |
| `swing/web/routes/schwab.py:91,106,121,396` | live | **(a)** | Route via `open_connection`. |
| `swing/web/routes/watchlist.py:80` | live | **(a)** | Route via `open_connection`. |
| `swing/web/view_models/schwab.py:446` | live | **(a)** | Route via `open_connection`. |

(`swing/cli.py:4769,4804,4866,5157` and `reconcile.py:13,140,432,506` matches are comments/docstrings — no code change.)

### OQ-C selected mechanism — Serialized shared audit-writer connection (rationale)

**Selected:** a single process-wide `sqlite3.Connection` to swing.db (opened `check_same_thread=False` via `open_connection`, busy_timeout from the cfg knob), used by the pipeline fetch hooks for ALL audit writes, with a **module-level `threading.Lock` in `audit_service`** wrapping every `BEGIN IMMEDIATE … COMMIT/ROLLBACK`.

**Why this over batching:** batching `record_call_start`/`record_call_finish` would defer the `start` commit and **break the in-flight-row visibility contract** (the `start` row MUST commit before the HTTP call so a mid-call crash leaves an `in_flight` row — `marketdata.py:551`). The serialized-connection mechanism preserves that contract exactly (each write still commits independently). Rejected: batching.

**The two cooperating pieces:**
1. **Module lock (`audit_service._AUDIT_WRITE_LOCK`)** — serializes all audit transactions *within a process*. **It wraps EVERY transaction-owning function in `audit_service`** — `record_call_start`, `record_call_finish`, `link_snapshot_and_stamp_account_hash` (`audit_service.py:206`), and `link_reconciliation_run` (`audit_service.py:266`) — not just start/finish (Codex R1 major #2: otherwise the "all audit transactions serialized" claim is false and a `link_*` write on a shared conn could collide). At most ONE audit `BEGIN IMMEDIATE` is ever active → eliminates audit-vs-audit SQLite write-lock contention regardless of how many connections exist. The pipeline and the web app run in *separate processes* (pipeline is a spawned subprocess under the lease), so each has its own lock instance; the contention being fixed is the 16 threads *inside the pipeline subprocess*. (The `link_*` functions run only in the low-concurrency reconciliation/snapshot flow, never on the shared pipeline conn, but are wrapped for a uniform invariant + future-proofing.)
2. **Shared connection (pipeline hooks)** — collapses the 16 per-hook connections to ONE, so the only remaining swing.db write contention is between this single audit connection and the *other* pipeline writers (candidates / archive / evaluate) — a drop from 16+ contenders to ~2. The 30 s `busy_timeout` covers that residual.

**Binding constraints preserved:**
- **Single-transaction discipline** — each audit write still owns its `BEGIN IMMEDIATE`/COMMIT/ROLLBACK; the lock only guarantees one active txn at a time (REQUIRED for a shared connection — two concurrent `BEGIN IMMEDIATE` on one connection is an error). The caller-held-tx rejection is preserved by moving the `conn.in_transaction` check INSIDE the lock (a shared conn is transiently in-tx while another serialized writer holds it; checking outside the lock would false-positive). Inside the lock the prior holder has always committed/rolled back, so a genuine caller-held tx is still correctly rejected for non-shared callers.
- **In-flight-row visibility** — `record_call_start` still COMMITS before returning; the lock is released between `start` and `finish`, so the HTTP call runs lock-free and a mid-call crash leaves a committed `in_flight` row.
- **Thread-safety** — the shared conn is opened `check_same_thread=False`; the lock serializes every access; the conn is never read outside audit (grounded above), so no unguarded cross-thread use.

**HTTP stays concurrent:** the lock is held only for the sub-ms INSERT/UPDATE, never across the HTTP call.

**Lock-wait telemetry (G2', kept):** measure the wall-clock of the `BEGIN IMMEDIATE` acquisition; log AFTER releasing the lock (never inside the critical section — Codex R2 major #3); emit for slow successes (≥1 s) AND failed acquisitions (busy_timeout exhausted). Durations + ints only (redaction-irrelevant). **The configured `busy_timeout` value is captured INSIDE the lock (conn idle, owned by this thread) and passed to the logger as a plain int — the after-lock logger NEVER touches the connection** (Codex R1 major #1: a `PRAGMA busy_timeout` read on the shared `check_same_thread=False` conn after releasing the lock would race a concurrent writer). The first instrumented live run reveals whether the bump+reduction sufficed (OQ-C is now shipped, but the telemetry still validates it). **Note (spec R2 minor #3 — banked, non-blocking):** the telemetry attributes the *audit victim*, not the *blocker*; instrumenting the dominant non-audit writers (candidates/archive/evaluate) with the same timed-`BEGIN IMMEDIATE` WARNING would localize the true contender. Deferred as an optional same-pattern extension for the first-live-run follow-on (out of V1 scope to bound blast radius).

---

## File Map

**Modify:**
- `swing/data/db.py` — add `DEFAULT_BUSY_TIMEOUT_MS = 30000` + `open_connection(...)`; route `connect()` (new `busy_timeout_ms` keyword) + `ensure_schema()` through it; route the 9 pre-migration backup `src_conn` opens through it.
- `swing/config.py` — add `db_busy_timeout_ms: int = 30000` to the `Web` dataclass.
- `swing/integrations/schwab/audit_service.py` — `_AUDIT_WRITE_LOCK` wrapping ALL FOUR transaction-owning functions (`record_call_start`, `record_call_finish`, `link_snapshot_and_stamp_account_hash`, `link_reconciliation_run`; in_transaction check moved inside the lock in each) + `_maybe_log_audit_lock_wait` G2' telemetry (start/finish only; `configured_ms` captured inside the lock).
- `swing/pipeline/runner.py` — open ONE shared audit connection in `_install_pipeline_marketdata_caches`; hooks use it instead of per-call `connect()`; return it as a 3rd element; close it at the run's `finally`.
- `swing/integrations/schwab/marketdata_ladder.py` — bind `exc` + log class+message (no `exc_info`) in both `except Exception` catch-alls; drop `# pragma: no cover`.
- `swing/data/backup.py` — route the `src` open through `open_connection` (preserve `mode=rw`).
- `swing/web/routes/{account,config,metrics,reconcile,schwab,watchlist}.py`, `swing/web/view_models/schwab.py`, `swing/web/app.py`, `swing/cli.py` — route live-swing.db direct opens through `open_connection`.
- `.gitignore` — OPTIONAL WAL sidecar patterns (non-blocking).

**Create (tests):**
- `tests/data/test_open_connection.py`
- `tests/data/test_connect_busy_timeout.py`
- `tests/integrations/schwab/test_audit_serialized_writer.py`
- `tests/integrations/schwab/test_audit_lock_wait_telemetry.py`
- `tests/integrations/schwab/test_ladder_stress_production_path.py`
- `tests/integrations/schwab/test_ladder_catchall_observability.py`
- `tests/data/test_backup_under_wal.py`
- (extend) `tests/test_config.py` for the new knob.

---

## Task 1: `open_connection` opener + `DEFAULT_BUSY_TIMEOUT_MS`

**Files:**
- Modify: `swing/data/db.py` (add near the top of the module, after imports / before `_create_pre_migration_backup`)
- Test: `tests/data/test_open_connection.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_open_connection.py
import sqlite3
import pytest
from pathlib import Path
from swing.data.db import open_connection, DEFAULT_BUSY_TIMEOUT_MS, ensure_schema


def test_default_busy_timeout_constant():
    assert DEFAULT_BUSY_TIMEOUT_MS == 30000


def _make_db(tmp_path: Path) -> Path:
    db = tmp_path / "swing.db"
    ensure_schema(db).close()  # creates a migrated WAL DB
    return db


def test_open_connection_applies_default_busy_timeout(tmp_path):
    db = _make_db(tmp_path)
    conn = open_connection(db)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_open_connection_keyword_override(tmp_path):
    db = _make_db(tmp_path)
    conn = open_connection(db, busy_timeout_ms=1234)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 1234
    finally:
        conn.close()


def test_open_connection_no_wal_reaffirm_by_default_but_db_stays_wal(tmp_path):
    # reaffirm_wal=False must NOT issue PRAGMA journal_mode=WAL, yet the DB is
    # already persistently WAL from ensure_schema -> journal_mode reads 'wal'.
    db = _make_db(tmp_path)
    conn = open_connection(db, reaffirm_wal=False)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_open_connection_reaffirm_wal_sets_wal(tmp_path):
    db = _make_db(tmp_path)
    conn = open_connection(db, reaffirm_wal=True)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_open_connection_uri_mode_rw_is_fail_closed(tmp_path):
    # mode=rw must REFUSE to create a missing DB (fail-closed); default rwc
    # would fabricate one. Proves uri=True forwarding preserves backup semantics.
    missing = tmp_path / "does-not-exist.db"
    uri = "file:" + missing.as_posix() + "?mode=rw"
    with pytest.raises(sqlite3.OperationalError):
        open_connection(uri, uri=True)
    assert not missing.exists()  # not fabricated


def test_open_connection_check_same_thread_false_allowed(tmp_path):
    db = _make_db(tmp_path)
    conn = open_connection(db, check_same_thread=False)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
    finally:
        conn.close()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/data/test_open_connection.py -q`
Expected: FAIL — `ImportError: cannot import name 'open_connection'` / `DEFAULT_BUSY_TIMEOUT_MS`.

- [ ] **Step 3: Implement the opener**

In `swing/data/db.py`, add (place the constant + function above the backup helpers, e.g. just after the module imports and any module-level constants):

```python
DEFAULT_BUSY_TIMEOUT_MS = 30000
"""Default per-connection SQLite busy_timeout (ms). 30 s is safe and fully
effective for the no-deadline OHLCV fetch path (the #23-amplified bulk of the
lock-contention degrade); it cannot rescue the 6 s-deadline quote path on its
own (see the serialized audit-writer mechanism). busy_timeout is per-connection
(NOT persistent like WAL), so it MUST be set on every connection."""


def open_connection(
    db_path_or_uri,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    reaffirm_wal: bool = False,
    uri: bool = False,
    check_same_thread: bool = True,
) -> sqlite3.Connection:
    """Public swing.db opener. Every swing.db connection routes through here so
    the busy_timeout is uniform (OQ-B). Applies, in THIS order:

      1. busy_timeout  : FIRST -- so any subsequent lock acquisition (a WAL
                         reaffirm, a BEGIN IMMEDIATE) is covered by the handler.
      2. foreign_keys=ON
      3. journal_mode=WAL : ONLY when reaffirm_wal=True (the ensure_schema path).
                         NOT on the hot connect() path -- the live DB is already
                         WAL (persistent in the file header); reaffirming per-open
                         is needless overhead and a needless lock point.

    ``uri=True`` forwards to ``sqlite3.connect(..., uri=True)`` so callers can
    pass a ``file:...?mode=rw`` URI and KEEP fail-closed semantics (backup source).
    ``check_same_thread=False`` is for the single shared serialized audit-writer
    connection (guarded by audit_service._AUDIT_WRITE_LOCK); do NOT use a shared
    connection across threads without that lock.
    """
    conn = sqlite3.connect(
        db_path_or_uri, uri=uri, check_same_thread=check_same_thread
    )
    conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
    conn.execute("PRAGMA foreign_keys=ON")
    if reaffirm_wal:
        conn.execute("PRAGMA journal_mode=WAL")
    return conn
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/data/test_open_connection.py -q`
Expected: PASS (all 7).

- [ ] **Step 5: Commit**

```bash
git add swing/data/db.py tests/data/test_open_connection.py
git commit -m "feat(data): centralized open_connection opener with busy_timeout-first ordering"
```

---

## Task 2: Route `connect()` + `ensure_schema()` through `open_connection`

**Files:**
- Modify: `swing/data/db.py:1128-1168` (`ensure_schema`, `connect`)
- Test: `tests/data/test_connect_busy_timeout.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_connect_busy_timeout.py
from pathlib import Path
from swing.data.db import connect, ensure_schema


def _make_db(tmp_path: Path) -> Path:
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db


def test_connect_applies_30s_busy_timeout(tmp_path):
    # ARITHMETIC (feedback_regression_test_arithmetic): pre-fix connect() used
    # sqlite3.connect(db_path) with no busy_timeout -> Python's default
    # timeout=5.0 surfaces as PRAGMA busy_timeout == 5000. Post-fix it is 30000.
    # Asserting == 30000 (which 5000 fails) is the genuine discriminator.
    db = _make_db(tmp_path)
    conn = connect(db)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
    finally:
        conn.close()


def test_connect_journal_mode_is_wal_regression_pin(tmp_path):
    # journal_mode reads 'wal' BOTH pre- and post-fix (persistent). This is a
    # regression PIN, not the discriminator.
    db = _make_db(tmp_path)
    conn = connect(db)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_connect_busy_timeout_keyword_override(tmp_path):
    db = _make_db(tmp_path)
    conn = connect(db, busy_timeout_ms=7777)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 7777
    finally:
        conn.close()


def test_ensure_schema_applies_busy_timeout_and_wal(tmp_path):
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/data/test_connect_busy_timeout.py -q`
Expected: FAIL — `busy_timeout` is `5000` (Python default), and `connect()` has no `busy_timeout_ms` keyword (`TypeError`).

- [ ] **Step 3: Implement the routing**

Replace `ensure_schema` body open (`db.py:1131-1133`):

```python
def ensure_schema(db_path: Path) -> sqlite3.Connection:
    """Create or upgrade the DB schema. Use from the CLI migrate command, NOT from app startup."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = open_connection(db_path, reaffirm_wal=True)
    # busy_timeout + foreign_keys + WAL are applied by open_connection (WAL FIRST
    # covered by busy_timeout). Remainder unchanged.
    current = _current_version(conn)
    ...
```

(Delete the now-redundant `conn.execute("PRAGMA journal_mode=WAL")` / `conn.execute("PRAGMA foreign_keys=ON")` lines at 1132-1133 — `open_connection(reaffirm_wal=True)` does both.)

Replace `connect` (`db.py:1153-1168`):

```python
def connect(
    db_path: Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
) -> sqlite3.Connection:
    """Open a connection for normal app use. Raises if schema is not current.

    WAL is NOT reaffirmed here -- the DB only reaches a current schema via
    ensure_schema, which sets WAL persistently (file-header property), so every
    DB connect() ever opens is already WAL. Reaffirming on the hot path buys
    nothing and adds a lock point (OQ-0 / R1 major #1).
    """
    if not db_path.exists():
        raise SchemaVersionMismatchError(
            f"DB not found at {db_path}. Run: swing db-migrate"
        )
    conn = open_connection(db_path, busy_timeout_ms=busy_timeout_ms, reaffirm_wal=False)
    current = _current_version(conn)
    if current != EXPECTED_SCHEMA_VERSION:
        conn.close()
        raise SchemaVersionMismatchError(
            f"DB schema version {current}, code expects {EXPECTED_SCHEMA_VERSION}. "
            "Run: swing db-migrate"
        )
    return conn
```

(Delete the old `conn = sqlite3.connect(db_path)` + `conn.execute("PRAGMA foreign_keys=ON")` at 1159-1160 — replaced by the `open_connection` call.)

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/data/test_connect_busy_timeout.py -q`
Expected: PASS (4).

- [ ] **Step 5: Run the existing db/migration suite to confirm no regression**

Run: `python -m pytest tests/data/ -q -m "not slow"`
Expected: PASS (no migration/version regression).

- [ ] **Step 6: Commit**

```bash
git add swing/data/db.py tests/data/test_connect_busy_timeout.py
git commit -m "feat(data): route connect()/ensure_schema() through open_connection (busy_timeout=30s, no hot-path WAL reaffirm)"
```

---

## Task 3: Config knob `cfg.web.db_busy_timeout_ms`

**Files:**
- Modify: `swing/config.py:373-403` (`Web` dataclass)
- Test: `tests/test_config.py` (extend)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py  (add)
from swing.config import Web, load_config


def test_web_db_busy_timeout_default():
    assert Web().db_busy_timeout_ms == 30000


def test_web_db_busy_timeout_from_toml(tmp_path):
    toml = tmp_path / "swing.config.toml"
    base = (tmp_path / "..").resolve()  # not used; full config below
    # Write a minimal-but-valid config by copying the repo template and adding the knob.
    import shutil, pathlib
    shutil.copy(pathlib.Path("swing.config.toml"), toml)
    text = toml.read_text(encoding="utf-8")
    assert "[web]" in text
    toml.write_text(text + "\ndb_busy_timeout_ms = 12000\n", encoding="utf-8")
    cfg = load_config(toml)
    assert cfg.web.db_busy_timeout_ms == 12000
```

(If `[web]` already has trailing keys, appending `db_busy_timeout_ms` under the file's existing `[web]` table works because TOML appends to the last-opened table; if the template's `[web]` is not the final table, instead insert the key immediately after the `[web]` header — the executing engineer should verify the template layout with `grep -n "^\[" swing.config.toml` and place the key inside the `[web]` table.)

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_config.py -k db_busy_timeout -q`
Expected: FAIL — `Web` has no `db_busy_timeout_ms` attribute / `load_config` raises `TypeError` (unexpected kwarg).

- [ ] **Step 3: Implement the field**

In `swing/config.py`, in the `Web` dataclass (after `pipeline_lease_wait_seconds`, ~line 390):

```python
    # SQLite lock-contention arc (OQ-A): per-connection busy_timeout (ms) for
    # all swing.db opens. 30 s default; runtime-tunable WITHOUT importing cfg
    # into swing/data/db.py (db.py owns the module-level DEFAULT_BUSY_TIMEOUT_MS;
    # this knob feeds open_connection's keyword override at the pipeline/web
    # callsites). Raising it helps the no-deadline OHLCV path; it cannot exceed
    # the 6 s quote-path caller deadline usefully.
    db_busy_timeout_ms: int = 30000
```

(`Config.load`/`from_toml` already builds `web=Web(**raw.get("web", {}))` at `config.py:543`, so the TOML key is parsed automatically.)

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_config.py -k db_busy_timeout -q`
Expected: PASS (2).

- [ ] **Step 5: Commit**

```bash
git add swing/config.py tests/test_config.py
git commit -m "feat(config): add web.db_busy_timeout_ms knob (default 30000)"
```

---

## Task 4: Serialized audit writes — module lock in `audit_service`

**Files:**
- Modify: `swing/integrations/schwab/audit_service.py:1-60` (imports + module lock) and `:86-118` (`record_call_start`), `:142-167` (`record_call_finish`), `:169-219` (`link_snapshot_and_stamp_account_hash`), `:244-276` (`link_reconciliation_run`)
- Test: `tests/integrations/schwab/test_audit_serialized_writer.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/integrations/schwab/test_audit_serialized_writer.py
import sqlite3
import threading
import pytest
from pathlib import Path
from swing.data.db import ensure_schema, connect, open_connection
from swing.integrations.schwab import audit_service
from swing.integrations.schwab.audit_service import CallerHeldTransactionError


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db


def test_caller_held_tx_still_rejected(tmp_path):
    db = _db(tmp_path)
    conn = connect(db)
    try:
        conn.execute("BEGIN IMMEDIATE")  # caller holds a tx
        with pytest.raises(CallerHeldTransactionError):
            audit_service.record_call_start(
                conn, ts="2026-06-06T00:00:00Z", endpoint="pricehistory",
                pipeline_run_id=None, surface="pipeline", environment="production",
            )
    finally:
        conn.rollback()
        conn.close()


def test_record_call_start_commits_in_flight_row_before_return(tmp_path):
    # In-flight visibility contract: the row is committed (visible from a SECOND
    # connection) immediately after record_call_start returns, before any finish.
    db = _db(tmp_path)
    writer = connect(db)
    reader = connect(db)
    try:
        call_id = audit_service.record_call_start(
            writer, ts="2026-06-06T00:00:00Z", endpoint="pricehistory",
            pipeline_run_id=None, surface="pipeline", environment="production",
        )
        row = reader.execute(
            "SELECT status FROM schwab_api_calls WHERE id=?", (call_id,)
        ).fetchone()
        assert row is not None  # committed + visible
    finally:
        writer.close()
        reader.close()


def test_shared_connection_concurrent_starts_all_land(tmp_path):
    # POST-FIX: ONE shared connection (check_same_thread=False) + the module lock
    # -> N concurrent record_call_start calls all land, zero OperationalError.
    db = _db(tmp_path)
    shared = open_connection(db, check_same_thread=False)
    errors = []
    ids = []
    lock_for_ids = threading.Lock()

    def worker(i):
        try:
            cid = audit_service.record_call_start(
                shared, ts="2026-06-06T00:00:00Z", endpoint="pricehistory",
                pipeline_run_id=None, surface="pipeline", environment="production",
            )
            with lock_for_ids:
                ids.append(cid)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    try:
        assert errors == []
        assert len(ids) == 16
        count = shared.execute("SELECT COUNT(*) FROM schwab_api_calls").fetchone()[0]
        assert count == 16
    finally:
        shared.close()
```

- [ ] **Step 2: Run to verify the concurrency test fails (and the others may pass)**

Run: `python -m pytest tests/integrations/schwab/test_audit_serialized_writer.py -q`
Expected: `test_shared_connection_concurrent_starts_all_land` FAILS — without the module lock, 16 threads issuing `BEGIN IMMEDIATE` on ONE shared connection raise `sqlite3.OperationalError: cannot start a transaction within a transaction` / `ProgrammingError`. (The other two pass against current code.)

- [ ] **Step 3: Implement the module lock**

In `swing/integrations/schwab/audit_service.py`, add at module level (after imports):

```python
import threading

# SQLite lock-contention arc (OQ-C): serialize ALL audit-row transactions within
# a process. With the shared pipeline audit connection this guarantees at most
# ONE BEGIN IMMEDIATE is active at a time (a single sqlite3 connection cannot run
# two concurrent transactions); it also removes audit-vs-audit write-lock
# contention even for distinct connections. Held only for the sub-ms INSERT/UPDATE
# -- NEVER across the HTTP call (start releases it before the HTTP; finish
# re-acquires).
_AUDIT_WRITE_LOCK = threading.Lock()
```

Rewrite `record_call_start` (preserve the surface-enum `ValueError` OUTSIDE the lock; move the `in_transaction` check INSIDE):

```python
    # Surface-enum validation stays outside the lock (pure input validation).
    if surface not in _SCHWAB_API_SURFACE_VALUES:
        raise ValueError(
            "surface must be one of "
            f"{_SCHWAB_API_SURFACE_VALUES}, got {surface!r}"
        )

    with _AUDIT_WRITE_LOCK:
        # in_transaction is checked INSIDE the lock: a shared audit connection is
        # transiently in-tx while another serialized writer holds it; checking
        # outside would false-positive. Inside the lock the prior holder has
        # committed/rolled back, so a genuine caller-held tx is still rejected.
        if conn.in_transaction:
            raise CallerHeldTransactionError(
                "record_call_start owns its own transaction; caller MUST NOT "
                "hold an open transaction. See CLAUDE.md gotcha 'Service-layer "
                "with conn:' + 'in_transaction auto-detect outer transaction "
                "guards re-introduce the very race the explicit lock was meant "
                "to close'."
            )
        conn.execute("BEGIN IMMEDIATE")
        try:
            call_id = repo.insert_in_flight(
                conn,
                ts=ts,
                endpoint=endpoint,
                pipeline_run_id=pipeline_run_id,
                surface=surface,
                environment=environment,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return call_id
```

Rewrite `record_call_finish` the same way (move `in_transaction` inside `with _AUDIT_WRITE_LOCK:`, wrap `BEGIN IMMEDIATE`/UPDATE/COMMIT/ROLLBACK in the lock):

```python
    with _AUDIT_WRITE_LOCK:
        if conn.in_transaction:
            raise CallerHeldTransactionError(
                "record_call_finish owns its own transaction; caller MUST NOT "
                "hold an open transaction. See CLAUDE.md gotcha 'Service-layer "
                "with conn:' + 'in_transaction auto-detect outer transaction "
                "guards re-introduce the very race the explicit lock was meant "
                "to close'."
            )
        conn.execute("BEGIN IMMEDIATE")
        try:
            repo.update_call_outcome(
                conn,
                call_id=call_id,
                http_status=http_status,
                response_time_ms=response_time_ms,
                rate_limit_remaining=rate_limit_remaining,
                signature_hash=signature_hash,
                status=status,
                error_message=error_message,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
```

- [ ] **Step 3b: Wrap the other two transaction-owning audit functions (Codex R1 major #2)**

`link_snapshot_and_stamp_account_hash` (~`audit_service.py:169`, `BEGIN IMMEDIATE` at ~206) and `link_reconciliation_run` (~`:244`, `BEGIN IMMEDIATE` at ~266) ALSO own transactions. Wrap each `BEGIN IMMEDIATE … COMMIT/ROLLBACK` in `with _AUDIT_WRITE_LOCK:` and move its `if conn.in_transaction: raise CallerHeldTransactionError(...)` check INSIDE the lock — identical structure to start/finish, MINUS the G2' timing (these run only in the low-concurrency reconciliation/snapshot flow, not on the contended pipeline conn). Example for `link_reconciliation_run`:

```python
    with _AUDIT_WRITE_LOCK:
        if conn.in_transaction:
            raise CallerHeldTransactionError(
                "link_reconciliation_run owns its own transaction; caller MUST "
                "NOT hold an open transaction. ..."  # keep the existing message verbatim
            )
        conn.execute("BEGIN IMMEDIATE")
        try:
            repo.update_call_linked_reconciliation_run(
                conn, call_id=call_id, reconciliation_run_id=reconciliation_run_id,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
```

Apply the same wrap to `link_snapshot_and_stamp_account_hash` (its body is a TWO-UPDATE combined transaction — wrap the WHOLE `BEGIN IMMEDIATE`/both-UPDATEs/COMMIT/ROLLBACK in the lock; move the `in_transaction` check inside; the inline helper `_stamp_account_hash_on_snapshot` has no own tx → leave it). Leave the verbatim docstrings/messages unchanged.

- [ ] **Step 3c: Add a regression test that a link-function still rejects a caller-held tx under the lock**

Add to `tests/integrations/schwab/test_audit_serialized_writer.py`:

```python
def test_link_reconciliation_run_still_rejects_caller_held_tx(tmp_path):
    db = _db(tmp_path)
    conn = connect(db)
    try:
        call_id = audit_service.record_call_start(
            conn, ts="2026-06-06T00:00:00Z", endpoint="accounts",
            pipeline_run_id=None, surface="cli", environment="production",
        )
        conn.execute("BEGIN IMMEDIATE")  # caller holds a tx
        with pytest.raises(CallerHeldTransactionError):
            audit_service.link_reconciliation_run(
                conn, call_id=call_id, reconciliation_run_id=1,
            )
    finally:
        conn.rollback()
        conn.close()
```

(Adapt `surface`/`endpoint`/`reconciliation_run_id` to whatever the existing `link_reconciliation_run` tests use; the assertion is that the caller-held-tx rejection survives the move inside the lock.)

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/integrations/schwab/test_audit_serialized_writer.py -q`
Expected: PASS (4).

- [ ] **Step 5: Run the existing audit_service suite (caller-held-tx + single-tx behavior unchanged)**

Run: `python -m pytest tests/integrations/schwab/ -q -m "not slow" -k "audit or call_start or call_finish"`
Expected: PASS (existing tests still green — the lock is transparent to single-threaded callers).

- [ ] **Step 6: Commit**

```bash
git add swing/integrations/schwab/audit_service.py tests/integrations/schwab/test_audit_serialized_writer.py
git commit -m "feat(schwab): serialize audit-row transactions via module lock (in_transaction check moved inside lock)"
```

---

## Task 5: G2' lock-wait telemetry in `audit_service`

**Files:**
- Modify: `swing/integrations/schwab/audit_service.py` (add `_maybe_log_audit_lock_wait` + timing in both write functions)
- Test: `tests/integrations/schwab/test_audit_lock_wait_telemetry.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/integrations/schwab/test_audit_lock_wait_telemetry.py
import logging
import threading
import time
import sqlite3
import pytest
from pathlib import Path
from swing.data.db import ensure_schema, open_connection
from swing.integrations.schwab import audit_service


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db


def test_failed_acquisition_logs_warning(tmp_path, caplog):
    # An external connection holds BEGIN IMMEDIATE; the audit conn has a TINY
    # busy_timeout -> record_call_start's BEGIN IMMEDIATE raises OperationalError;
    # on the way out a WARNING reports the wait + busy_timeout.
    db = _db(tmp_path)
    holder = open_connection(db, busy_timeout_ms=30000)
    holder.execute("BEGIN IMMEDIATE")
    holder.execute(
        "INSERT INTO schwab_api_calls (ts, endpoint, surface, environment, status) "
        "VALUES ('2026-06-06T00:00:00Z','pricehistory','pipeline','production','in_flight')"
    )  # holds the write lock
    audit_conn = open_connection(db, busy_timeout_ms=1)  # 1 ms -> will time out
    try:
        with caplog.at_level(logging.WARNING, logger="swing.integrations.schwab.audit_service"):
            with pytest.raises(sqlite3.OperationalError):
                audit_service.record_call_start(
                    audit_conn, ts="2026-06-06T00:00:01Z", endpoint="pricehistory",
                    pipeline_run_id=None, surface="pipeline", environment="production",
                )
        msgs = [r.getMessage() for r in caplog.records]
        assert any("FAILED" in m and "busy_timeout" in m for m in msgs)
        # redaction-irrelevant: no exc_info / traceback attached
        assert all(r.exc_info is None for r in caplog.records)
    finally:
        holder.rollback()
        holder.close()
        audit_conn.close()


def test_slow_success_logs_warning(tmp_path, caplog, monkeypatch):
    # Force a slow BEGIN IMMEDIATE by monkeypatching the timer so the measured
    # wait exceeds the threshold even though the write succeeds.
    db = _db(tmp_path)
    conn = open_connection(db, busy_timeout_ms=30000)
    seq = iter([0.0, 2.0])  # t0=0.0 before BEGIN, t1=2.0 after -> 2.0s wait

    real_monotonic = time.monotonic

    def fake_monotonic():
        try:
            return next(seq)
        except StopIteration:
            return real_monotonic()

    monkeypatch.setattr(audit_service.time, "monotonic", fake_monotonic)
    try:
        with caplog.at_level(logging.WARNING, logger="swing.integrations.schwab.audit_service"):
            audit_service.record_call_start(
                conn, ts="2026-06-06T00:00:00Z", endpoint="pricehistory",
                pipeline_run_id=None, surface="pipeline", environment="production",
            )
        msgs = [r.getMessage() for r in caplog.records]
        assert any("slow" in m.lower() and "busy_timeout" in m for m in msgs)
    finally:
        conn.close()


def test_fast_success_does_not_log(tmp_path, caplog):
    db = _db(tmp_path)
    conn = open_connection(db, busy_timeout_ms=30000)
    try:
        with caplog.at_level(logging.WARNING, logger="swing.integrations.schwab.audit_service"):
            audit_service.record_call_start(
                conn, ts="2026-06-06T00:00:00Z", endpoint="pricehistory",
                pipeline_run_id=None, surface="pipeline", environment="production",
            )
        assert [r for r in caplog.records if "BEGIN IMMEDIATE" in r.getMessage()] == []
    finally:
        conn.close()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/integrations/schwab/test_audit_lock_wait_telemetry.py -q`
Expected: FAIL — no WARNING is emitted (telemetry not implemented); `audit_service.time` may not exist.

- [ ] **Step 3: Implement the telemetry**

Ensure `import time` and `import logging` + a module `log = logging.getLogger(__name__)` exist in `audit_service.py` (add if missing). Add constant + helper:

```python
_SLOW_ACQUIRE_WARN_THRESHOLD_S = 1.0


def _maybe_log_audit_lock_wait(op, waited_s, busy_failed, configured_ms):
    """G2' lock-wait visibility. Called AFTER the lock is released (never inside
    the critical section -- logging I/O would extend the contention window). The
    `configured_ms` busy_timeout value is captured by the CALLER while still
    holding the lock and passed in as a plain int -- this function NEVER touches
    the connection (Codex R1 major #1: a PRAGMA read on the shared
    check_same_thread=False conn after lock release would race a concurrent
    writer). Emits a WARNING for failed acquisitions (busy_timeout exhausted) and
    for slow successful ones (>= threshold). Durations + ints only -> redaction-
    irrelevant.
    """
    if not busy_failed and (waited_s is None or waited_s < _SLOW_ACQUIRE_WARN_THRESHOLD_S):
        return
    if busy_failed:
        log.warning(
            "audit %s: BEGIN IMMEDIATE FAILED (database is locked) after %.3fs "
            "(busy_timeout=%sms)", op, waited_s or 0.0, configured_ms,
        )
    else:
        log.warning(
            "audit %s: slow BEGIN IMMEDIATE acquisition %.3fs (busy_timeout=%sms)",
            op, waited_s, configured_ms,
        )
```

Wrap the timing in `record_call_start` (and identically in `record_call_finish`, with `op="record_call_finish"`). **`configured_ms` is read INSIDE the lock, before the `in_transaction` check (conn idle, owned by this thread), so the after-lock logger never touches the connection:**

```python
    if surface not in _SCHWAB_API_SURFACE_VALUES:   # (start only) stays outside lock
        raise ValueError(...)

    waited_s = None
    busy_failed = False
    configured_ms = None
    try:
        with _AUDIT_WRITE_LOCK:
            try:
                configured_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            except Exception:  # noqa: BLE001 -- diagnostic only
                configured_ms = None
            if conn.in_transaction:
                raise CallerHeldTransactionError(...)
            _t0 = time.monotonic()
            try:
                conn.execute("BEGIN IMMEDIATE")
                waited_s = time.monotonic() - _t0
                call_id = repo.insert_in_flight(conn, ...)
                conn.commit()
            except sqlite3.OperationalError:
                waited_s = time.monotonic() - _t0
                busy_failed = True
                conn.rollback()
                raise
            except Exception:
                conn.rollback()
                raise
    finally:
        _maybe_log_audit_lock_wait("record_call_start", waited_s, busy_failed, configured_ms)
    return call_id
```

(For `record_call_finish`, the same structure with `repo.update_call_outcome` and `op="record_call_finish"`; it has no `return` value. `CallerHeldTransactionError` raised inside the `with` leaves `waited_s=None`/`busy_failed=False` so the `finally` logs nothing. The two `link_*` functions from Task 4 Step 3b do NOT get this timing — they are off the contended path.)

Confirm `import sqlite3` is present in the module (it is — used in type hints).

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/integrations/schwab/test_audit_lock_wait_telemetry.py -q`
Expected: PASS (3).

- [ ] **Step 5: Re-run the serialized-writer suite (no regression from the timing wrapper)**

Run: `python -m pytest tests/integrations/schwab/test_audit_serialized_writer.py -q`
Expected: PASS (3).

- [ ] **Step 6: Commit**

```bash
git add swing/integrations/schwab/audit_service.py tests/integrations/schwab/test_audit_lock_wait_telemetry.py
git commit -m "feat(schwab): G2' lock-wait telemetry for audit BEGIN IMMEDIATE (logged after lock release; slow + failed)"
```

---

## Task 6: Shared serialized audit connection in the pipeline hooks

**Files:**
- Modify: `swing/pipeline/runner.py` — `_install_pipeline_marketdata_caches` (~322-470: open shared conn, rewrite `_quote_hook`/`_bars_hook`, return 3-tuple); the callsite (~784); init `audit_conn=None` before the run `try` (~703); close in the run `finally` (~1014). Add `open_connection` to the `db` import.
- Test: `tests/integrations/schwab/test_pipeline_shared_audit_conn.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integrations/schwab/test_pipeline_shared_audit_conn.py
from pathlib import Path
from swing.data.db import ensure_schema
from swing.pipeline import runner
from swing.config import load_config


class _FakeClient:
    """Minimal stand-in so _install_pipeline_marketdata_caches builds hooks."""


def test_install_returns_shared_audit_conn_with_knob_busy_timeout(tmp_path, monkeypatch):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    cfg = load_config(Path("swing.config.toml"))
    cfg = cfg.__class__(**{**cfg.__dict__})  # shallow copy ok; see note
    # Point the config at the tmp DB + a custom busy_timeout knob.
    monkeypatch.setattr(cfg.paths, "db_path", db, raising=False)
    object.__setattr__(cfg.web, "db_busy_timeout_ms", 21000)

    price_cache, ohlcv_cache, audit_conn = runner._install_pipeline_marketdata_caches(
        cfg, _FakeClient(), pipeline_run_id=None,
    )
    try:
        assert audit_conn is not None
        assert audit_conn.execute("PRAGMA busy_timeout").fetchone()[0] == 21000
    finally:
        if audit_conn is not None:
            audit_conn.close()


def test_install_returns_none_triple_without_client(tmp_path):
    cfg = load_config(Path("swing.config.toml"))
    price_cache, ohlcv_cache, audit_conn = runner._install_pipeline_marketdata_caches(
        cfg, None, pipeline_run_id=None,
    )
    assert (price_cache, ohlcv_cache, audit_conn) == (None, None, None)
```

(Note: `cfg` is frozen dataclasses; the executing engineer should construct the tuned cfg via the project's standard test config builder if `object.__setattr__` on a frozen nested dataclass is awkward. The behavioral assertions are: 3-tuple returned; `audit_conn` busy_timeout matches `cfg.web.db_busy_timeout_ms`; `(None, None, None)` when no client. Adapt construction to the existing fixtures in `tests/pipeline/`.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/integrations/schwab/test_pipeline_shared_audit_conn.py -q`
Expected: FAIL — `_install_pipeline_marketdata_caches` returns a 2-tuple (`ValueError: not enough values to unpack`).

- [ ] **Step 3: Implement the shared connection**

In `swing/pipeline/runner.py`:

(a) Ensure the import includes `open_connection`:
```python
from swing.data.db import connect, open_connection  # (extend existing import)
```

(b) In `_install_pipeline_marketdata_caches`, change the no-client early return (~348):
```python
    if schwab_client is None:
        return None, None, None
```

(c) After `ohlcv_cache = OhlcvCache(cfg)` (~358), open the shared audit connection:
```python
    # SQLite lock-contention arc (OQ-C): ONE shared serialized audit-writer
    # connection for ALL pipeline market-data audit writes, replacing the
    # ≤16 per-hook connect()/close() pairs. check_same_thread=False because the
    # executor runs the hooks on worker threads; audit_service._AUDIT_WRITE_LOCK
    # serializes every BEGIN IMMEDIATE on it. The market-data path uses `conn`
    # ONLY for audit (record_call_start/finish), so this is safe.
    audit_conn = open_connection(
        cfg.paths.db_path,
        busy_timeout_ms=cfg.web.db_busy_timeout_ms,
        reaffirm_wal=False,
        check_same_thread=False,
    )
```

(d) Rewrite `_quote_hook` (remove the per-call `connect`/`close`; use `audit_conn`):
```python
    def _quote_hook(ticker: str) -> tuple[float, str]:
        snap, provider_tag = fetch_quote_via_ladder(
            ticker,
            cfg=cfg,
            schwab_client=schwab_client,
            yfinance_fallback_fn=_yf_quote_fallback,
            conn=audit_conn,
            surface="pipeline",
            pipeline_run_id=pipeline_run_id,
        )
        return (snap.price, provider_tag)
```

(e) Rewrite `_bars_hook` the same way (remove `conn = connect(...)` / `finally: conn.close()`, pass `conn=audit_conn`).

(f) Change the return (~470):
```python
    price_cache.set_ladder_fetcher(_quote_hook)
    ohlcv_cache.set_ladder_bars_fetcher(_bars_hook)
    return price_cache, ohlcv_cache, audit_conn
```

(g) At the run callsite, init before the outer `try:` (insert immediately before line 703 `        try:`):
```python
        audit_conn = None
```

(h) Update the unpack (~784):
```python
            price_cache, ohlcv_cache, audit_conn = _install_pipeline_marketdata_caches(
                cfg, schwab_client, pipeline_run_id=lease.run_id,
            )
```

(i) Close it in the run's existing `finally` (the `finally: hb.stop()` at ~1014):
```python
    finally:
        hb.stop()
        if audit_conn is not None:
            audit_conn.close()
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/integrations/schwab/test_pipeline_shared_audit_conn.py -q`
Expected: PASS (2).

- [ ] **Step 5: Run the pipeline suite to confirm the 3-tuple change is fully propagated**

Run: `python -m pytest tests/pipeline/ -q -m "not slow"`
Expected: PASS — grep first for any OTHER caller of `_install_pipeline_marketdata_caches` (`grep -rn "_install_pipeline_marketdata_caches" swing/ tests/`) and update every unpack to 3 values.

- [ ] **Step 6: Commit**

```bash
git add swing/pipeline/runner.py tests/integrations/schwab/test_pipeline_shared_audit_conn.py
git commit -m "feat(pipeline): single shared serialized audit-writer connection for market-data hooks (collapses ≤16 connections to 1)"
```

---

## Task 7: Production-path concurrency stress test, split by failure point

**Files:**
- Test only: `tests/integrations/schwab/test_ladder_stress_production_path.py` (the implementation already exists from Tasks 1-6)

**Why this task:** the lower-level Task 4 test proves a bare INSERT can lock; this drives the REAL `record_call_start → HTTP → record_call_finish` sequence through the ladder wrapper under concurrency, splitting the pre-fix assertion by WHERE the lock fails (Codex R2 major #4: `record_call_start` commits before the HTTP, so "no audit row" is only correct for a start-lock).

- [ ] **Step 1: Write the test**

```python
# tests/integrations/schwab/test_ladder_stress_production_path.py
import sqlite3
import threading
import time
import pytest
from pathlib import Path
from swing.data.db import ensure_schema, open_connection
from swing.integrations.schwab import marketdata


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db


def _external_lock_holder(db: Path, hold_seconds: float, release_evt: threading.Event):
    """Hold the SQLite write lock for `hold_seconds` (simulating a candidates/
    archive/evaluate writer) so an audit BEGIN IMMEDIATE must wait."""
    conn = open_connection(db, busy_timeout_ms=30000)
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(
        "INSERT INTO schwab_api_calls (ts, endpoint, surface, environment, status) "
        "VALUES ('2026-06-06T00:00:00Z','probe','pipeline','production','in_flight')"
    )
    release_evt.wait(timeout=hold_seconds)
    conn.commit()
    conn.close()


def test_forced_start_lock_leaves_no_audit_row(tmp_path):
    # PRE-FIX shape: tiny busy_timeout + external holder during start ->
    # record_call_start's BEGIN IMMEDIATE times out BEFORE the insert commits.
    db = _db(tmp_path)
    audit_conn = open_connection(db, busy_timeout_ms=1)  # 1ms -> times out
    release = threading.Event()
    holder = threading.Thread(target=_external_lock_holder, args=(db, 2.0, release))
    holder.start()
    time.sleep(0.05)  # ensure the holder owns the lock first
    try:
        with pytest.raises(sqlite3.OperationalError):
            marketdata.get_price_history(
                _StubClient(), audit_conn, "AAPL",
                period_type="year", period=5, frequency_type="daily", frequency=1,
                start_dt=None, end_dt=None, surface="pipeline",
                environment="production", pipeline_run_id=None,
            )
        # start never committed -> no audit row
        count = audit_conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls WHERE endpoint='pricehistory'"
        ).fetchone()[0]
        assert count == 0
    finally:
        release.set()
        holder.join()
        audit_conn.close()


def test_forced_finish_lock_leaves_in_flight_row(tmp_path):
    # PRE-FIX shape: start commits (no contention), THEN an external holder grabs
    # the lock during the injected HTTP latency window so record_call_finish's
    # BEGIN IMMEDIATE times out -> the committed in_flight row REMAINS, unfinalized.
    db = _db(tmp_path)
    audit_conn = open_connection(db, busy_timeout_ms=1)
    release = threading.Event()
    # Stub client whose HTTP call blocks until the external holder is engaged.
    holder_started = threading.Event()

    def _on_http():
        # spawn the lock holder mid-HTTP, then let finish contend
        holder = threading.Thread(target=_external_lock_holder, args=(db, 2.0, release))
        holder.start()
        holder_started.set()
        time.sleep(0.1)
        return holder

    client = _StubClient(on_http=_on_http)
    try:
        with pytest.raises(sqlite3.OperationalError):
            marketdata.get_price_history(
                client, audit_conn, "MSFT",
                period_type="year", period=5, frequency_type="daily", frequency=1,
                start_dt=None, end_dt=None, surface="pipeline",
                environment="production", pipeline_run_id=None,
            )
        # start committed -> exactly one in_flight row, terminal fields NULL
        rows = audit_conn.execute(
            "SELECT status, http_status FROM schwab_api_calls WHERE endpoint='pricehistory'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "in_flight"
        assert rows[0][1] is None
    finally:
        release.set()
        audit_conn.close()


def test_post_fix_30s_all_attempts_complete(tmp_path):
    # POST-FIX: 30s busy_timeout + external holder that releases within budget ->
    # the audit writes drain and complete; no OperationalError.
    db = _db(tmp_path)
    audit_conn = open_connection(db, busy_timeout_ms=30000, check_same_thread=False)
    release = threading.Event()
    holder = threading.Thread(target=_external_lock_holder, args=(db, 0.5, release))
    holder.start()
    time.sleep(0.05)
    try:
        # Should NOT raise -- waits up to 30s, holder releases at 0.5s.
        result = marketdata.get_price_history(
            _StubClient(), audit_conn, "NVDA",
            period_type="year", period=5, frequency_type="daily", frequency=1,
            start_dt=None, end_dt=None, surface="pipeline",
            environment="production", pipeline_run_id=None,
        )
        assert result is not None
        rows = audit_conn.execute(
            "SELECT status FROM schwab_api_calls WHERE endpoint='pricehistory'"
        ).fetchall()
        assert len(rows) == 1 and rows[0][0] == "success"
    finally:
        release.set()
        holder.join()
        audit_conn.close()
```

**Implementation note for the engineer (test scaffolding):** `marketdata.get_price_history` calls into schwabdev via the client. Build `_StubClient` to mirror the existing pattern in `tests/integrations/schwab/` (search for the established mock client / `get_price_history` test setup — e.g. `tests/integrations/schwab/test_marketdata*.py`). The stub must (a) return a valid mappable `price_history` payload so the mapper + `record_call_finish(status='success')` path runs in the post-fix test, and (b) accept an `on_http` callback invoked inside the mocked schwabdev call to interleave the external lock holder for the finish-lock case. Reuse the project's canonical valid-payload fixture rather than inventing one. If `get_price_history`'s exact signature differs from the call above, match the grounded signature (`marketdata.py:507+`).

**ARITHMETIC (feedback_regression_test_arithmetic):** the discriminator is `busy_timeout_ms`: at `1` ms the audit `BEGIN IMMEDIATE` times out while the external holder (≥0.5 s) owns the lock → `OperationalError` (pre-fix shape, split by start vs finish); at `30000` ms the same holder releases at 0.5 s → the audit write drains and succeeds (post-fix). The two regimes flip the outcome on the timeout value alone.

- [ ] **Step 2: Run to verify the post-fix test passes and the failure-point tests assert the right row state**

Run: `python -m pytest tests/integrations/schwab/test_ladder_stress_production_path.py -q`
Expected: PASS (3) — `forced_start_lock` → 0 rows; `forced_finish_lock` → 1 `in_flight` row; `post_fix` → 1 `success` row, no error.

- [ ] **Step 3: Commit**

```bash
git add tests/integrations/schwab/test_ladder_stress_production_path.py
git commit -m "test(schwab): production-path concurrency stress split by failure point (start-lock=no row, finish-lock=in_flight row)"
```

---

## Task 8: Ladder catch-all observability (class + message; no exc_info)

**Files:**
- Modify: `swing/integrations/schwab/marketdata_ladder.py:325-334` (quote catch-all), `:456-463` (window catch-all)
- Test: `tests/integrations/schwab/test_ladder_catchall_observability.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/integrations/schwab/test_ladder_catchall_observability.py
import logging
import sqlite3
import pytest
from swing.integrations.schwab import marketdata_ladder


def test_window_catchall_logs_class_and_message_no_exc_info(monkeypatch, caplog):
    def _boom(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(marketdata_ladder, "get_price_history", _boom)

    def _yf(ticker, start, end):
        return _DummyWindow()

    with caplog.at_level(logging.WARNING, logger="swing.integrations.schwab.marketdata_ladder"):
        window, provider = marketdata_ladder.fetch_window_via_ladder(
            "AAPL", start=None, end=None, cfg=_cfg(), schwab_client=object(),
            yfinance_fallback_fn=_yf, conn=_conn(), surface="pipeline",
            pipeline_run_id=None,
        )
    assert provider == "yfinance"
    rec = [r for r in caplog.records if "AAPL" in r.getMessage()][-1]
    assert "OperationalError" in rec.getMessage()
    assert "database is locked" in rec.getMessage()
    assert rec.exc_info is None  # NO traceback


def test_window_catchall_message_is_redacted(monkeypatch, caplog):
    # The setLogRecordFactory content-redaction wrapper must scrub a planted
    # secret in the exception message (message path, not exc_info).
    from swing.integrations.schwab.log_redaction import (
        ensure_schwab_log_redaction_factory_installed,
    )
    ensure_schwab_log_redaction_factory_installed()
    secret = "A" * 40  # 40-hex-ish -> heuristic redaction target
    def _boom(*a, **k):
        raise sqlite3.OperationalError(f"locked token={secret}")
    monkeypatch.setattr(marketdata_ladder, "get_price_history", _boom)
    with caplog.at_level(logging.WARNING, logger="swing.integrations.schwab.marketdata_ladder"):
        marketdata_ladder.fetch_window_via_ladder(
            "AAPL", start=None, end=None, cfg=_cfg(), schwab_client=object(),
            yfinance_fallback_fn=lambda t, s, e: _DummyWindow(),
            conn=_conn(), surface="pipeline", pipeline_run_id=None,
        )
    assert all(secret not in r.getMessage() for r in caplog.records)


def test_quote_catchall_logs_class_and_message(monkeypatch, caplog):
    def _boom(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(marketdata_ladder, "get_quotes_batch", _boom)
    with caplog.at_level(logging.WARNING, logger="swing.integrations.schwab.marketdata_ladder"):
        entry, provider = marketdata_ladder.fetch_quote_via_ladder(
            "AAPL", cfg=_cfg(), schwab_client=object(),
            yfinance_fallback_fn=lambda t: _DummySnap(),
            conn=_conn(), surface="pipeline", pipeline_run_id=None,
        )
    assert provider == "yfinance"
    rec = [r for r in caplog.records if "AAPL" in r.getMessage()][-1]
    assert "OperationalError" in rec.getMessage()
    assert "database is locked" in rec.getMessage()
    assert rec.exc_info is None
```

**Scaffolding note:** `_cfg()`, `_conn()`, `_DummyWindow()`, `_DummySnap()` must mirror the existing ladder tests — search `tests/integrations/schwab/test_marketdata_ladder*.py` for the established fixtures (a real `cfg`, a `connect()`'d tmp DB conn, and the dummy window/snapshot shapes the ladder returns). Reuse them; do not invent new shapes. The redaction test depends on the actual `setLogRecordFactory` heuristic in `swing/integrations/schwab/log_redaction.py` — confirm the planted-secret shape matches a pattern the factory redacts (32+ hex / 24+ b64); adjust the sentinel to a redacted shape if needed.

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/integrations/schwab/test_ladder_catchall_observability.py -q`
Expected: FAIL — current catch-alls log only the ticker (no class/message), so the `"OperationalError"`/`"database is locked"` assertions fail.

- [ ] **Step 3: Implement the catch-all logging**

In `marketdata_ladder.py`, quote catch-all (~325):
```python
    except Exception as exc:
        log.warning(
            "fetch_quote_via_ladder: unexpected error from T-C.1 wrapper for "
            "%s: %s: %s; falling back to yfinance",
            ticker, type(exc).__name__, exc,
        )
        entry = yfinance_fallback_fn(ticker)
        return (entry, "yfinance")
```

Window catch-all (~456):
```python
    except Exception as exc:
        log.warning(
            "fetch_window_via_ladder: unexpected error from T-C.1 wrapper for "
            "%s: %s: %s; falling back to yfinance",
            ticker, type(exc).__name__, exc,
        )
        window = yfinance_fallback_fn(ticker, start, end)
        _persist_window_to_archive(ticker, window, "yfinance", cache_dir)
        return (window, "yfinance")
```

Delete the `# pragma: no cover — defensive` comment on both arms (now exercised). Do NOT use `exc_info=True` (traceback frames bypass message-level redaction).

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/integrations/schwab/test_ladder_catchall_observability.py -q`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add swing/integrations/schwab/marketdata_ladder.py tests/integrations/schwab/test_ladder_catchall_observability.py
git commit -m "feat(schwab): ladder catch-alls log exception class+message (redaction-safe, no exc_info)"
```

---

## Task 9: Backup source `busy_timeout` (preserve fail-closed `mode=rw`)

**Files:**
- Modify: `swing/data/backup.py:66-67` (the `src` open); `swing/data/db.py` (the 9 `src_conn` opens in `_create_pre_*_migration_backup`)
- Test: `tests/data/test_backup_under_wal.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_backup_under_wal.py
import sqlite3
import pytest
from pathlib import Path
from swing.data.db import ensure_schema, open_connection
from swing.data.backup import do_backup


def test_backup_under_wal_with_open_writer_passes_integrity(tmp_path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    # An open writer connection (simulating a live pipeline writer).
    writer = open_connection(db, busy_timeout_ms=30000)
    writer.execute("BEGIN IMMEDIATE")
    writer.execute(
        "INSERT INTO schwab_api_calls (ts, endpoint, surface, environment, status) "
        "VALUES ('2026-06-06T00:00:00Z','pricehistory','pipeline','production','in_flight')"
    )
    writer.commit()
    dest_dir = tmp_path / "backups"
    try:
        final = do_backup(db, dest_dir)
        chk = sqlite3.connect(final)
        try:
            assert chk.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            chk.close()
    finally:
        writer.close()


def test_backup_source_still_fail_closed_on_missing_db(tmp_path):
    # mode=rw must refuse a missing source (NOT create it) -- preserved after
    # routing through open_connection.
    missing = tmp_path / "nope.db"
    with pytest.raises(sqlite3.OperationalError):
        do_backup(missing, tmp_path / "backups")
    assert not missing.exists()
```

(`do_backup` signature: confirm against `swing/data/backup.py` — it is `do_backup(db_path, dest_dir, now=None)` per the grounded `compute_backup_destination` usage. Adapt arg order if the grounded signature differs.)

- [ ] **Step 2: Run to verify the integrity test passes already (backup is WAL-safe) and confirm fail-closed**

Run: `python -m pytest tests/data/test_backup_under_wal.py -q`
Expected: both PASS even pre-change (backup API is already WAL-safe + `mode=rw` already fail-closed). These are **regression pins** guarding the §5 backup decision. If `test_backup_source_still_fail_closed_on_missing_db` is already covered by an existing test, keep this as an explicit pin anyway.

- [ ] **Step 3: Implement the busy_timeout on the source opens**

In `swing/data/backup.py` (~67), replace:
```python
    src = sqlite3.connect(src_uri, uri=True)
```
with:
```python
    # Route the SOURCE open through the centralized opener so a weekly backup
    # taken mid-pipeline doesn't fail fast on the 5 s default. mode=rw fail-closed
    # semantics are PRESERVED (uri=True forwards the ?mode=rw URI). The online
    # backup() API stays WAL-safe + unchanged.
    from swing.data.db import open_connection, DEFAULT_BUSY_TIMEOUT_MS
    src = open_connection(src_uri, uri=True, busy_timeout_ms=DEFAULT_BUSY_TIMEOUT_MS)
```
(Place the import at module top if `backup.py` does not already import from `db` — check for an import cycle; `backup.py` is imported by `db.py`? No — `db.py` does not import `backup.py` at module level [backup is invoked lazily], so a top-level `from swing.data.db import ...` in `backup.py` is safe. Verify with `grep -n "import backup\|from swing.data.backup" swing/data/db.py` → expect no module-level import.)

In `swing/data/db.py`, in EACH `_create_pre_*_migration_backup` helper, replace `src_conn = sqlite3.connect(src_path)` with:
```python
    src_conn = open_connection(src_path, busy_timeout_ms=DEFAULT_BUSY_TIMEOUT_MS)
```
(9 occurrences: lines ~318, 451, 475, 500, 525, 552, 579, 602, 630. Leave every `dest_conn = sqlite3.connect(backup_path)` and the `:352` integrity read-back unchanged — fresh/private files.)

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/data/test_backup_under_wal.py tests/data/ -q -m "not slow" -k "backup"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/data/backup.py swing/data/db.py tests/data/test_backup_under_wal.py
git commit -m "feat(data): apply busy_timeout to backup source opens (mode=rw fail-closed preserved)"
```

---

## Task 10: Route web / view-model / app / cli live-swing.db direct opens through `open_connection`

**Files:**
- Modify: `swing/web/routes/account.py` (89,120,149); `config.py` (71,141,224); `metrics.py` (54,249); `reconcile.py` (147,437,513); `schwab.py` (91,106,121,396); `watchlist.py` (80); `swing/web/view_models/schwab.py` (446); `swing/web/app.py` (389); `swing/cli.py` (149,211 src,227,5160,5201)
- Test: `tests/web/test_live_opens_routed.py`

- [ ] **Step 1: Write the failing test (structural + functional spot-check)**

```python
# tests/web/test_live_opens_routed.py
import re
from pathlib import Path
import pytest

# ALIAS-AWARE pattern (Codex R1 major #3): catches BOTH `sqlite3.connect(` AND the
# `import sqlite3 as _sqlite3` alias `_sqlite3.connect(` used in app.py / cli.py.
# `\b` before the optional `_` so we don't match a longer identifier ending in
# "sqlite3".
_RAW_CONNECT = re.compile(r"(?<![\w.])_?sqlite3\.connect\(")

# These files have ZERO legitimate raw opens after routing — every open is a
# live swing.db open that must go through open_connection.
_LIVE_OPEN_FILES = [
    "swing/web/routes/account.py",
    "swing/web/routes/config.py",
    "swing/web/routes/metrics.py",
    "swing/web/routes/reconcile.py",
    "swing/web/routes/schwab.py",
    "swing/web/routes/watchlist.py",
    "swing/web/view_models/schwab.py",
    "swing/web/app.py",
]


def _raw_call_sites(rel):
    text = Path(rel).read_text(encoding="utf-8")
    return [
        ln for ln in text.splitlines()
        if _RAW_CONNECT.search(ln) and not ln.lstrip().startswith("#")
    ]


@pytest.mark.parametrize("rel", _LIVE_OPEN_FILES)
def test_no_raw_sqlite3_connect_for_live_db(rel):
    # Every live-swing.db open routes through open_connection (busy_timeout).
    # A raw sqlite3.connect / _sqlite3.connect for the live DB is the regression.
    sites = _raw_call_sites(rel)
    assert sites == [], f"{rel} still has raw sqlite3 connect: {sites}"


def test_cli_remaining_raw_connect_are_backup_dest_only():
    # cli.py legitimately KEEPS the db-migrate backup DESTINATION open
    # (dst = _sqlite3.connect(backup_path)). EVERY OTHER raw open (the divergence
    # check :149, the db-migrate src :211, the version probe :227, the two
    # diagnose --db opens :5160/:5201) must route through open_connection. So the
    # ONLY raw connect remaining must reference `backup_path`; anything else is an
    # unrouted live open and fails here.
    sites = _raw_call_sites("swing/cli.py")
    offenders = [ln for ln in sites if "backup_path" not in ln]
    assert offenders == [], f"unrouted live open(s) in cli.py: {offenders}"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/web/test_live_opens_routed.py -q`
Expected: FAIL — each route file still contains a raw `sqlite3.connect(`/`_sqlite3.connect(`, and `cli.py` has raw live opens (`:149/:211/:227/:5160/:5201`) that don't reference `backup_path`.

- [ ] **Step 3: Mechanical replacement**

In each listed file, replace `conn = sqlite3.connect(<db_path_expr>)` with `conn = open_connection(<db_path_expr>, busy_timeout_ms=cfg.web.db_busy_timeout_ms)` where `cfg` is in scope; where `cfg` is NOT readily in scope, use `open_connection(<db_path_expr>)` (default const). Add `from swing.data.db import open_connection` to each file's imports (and drop the now-unused `import sqlite3` ONLY if no other `sqlite3.*` usage remains — keep it if `sqlite3.OperationalError` etc. is still referenced).

Per-file notes (grounded):
- `account.py` 89/120/149, `metrics.py` 54/249, `schwab.py` 91/106/121/396, `watchlist.py` 80, `view_models/schwab.py` 446 — `cfg` (or `cfg.paths.db_path`) is the open arg; pass `busy_timeout_ms=cfg.web.db_busy_timeout_ms`.
- `config.py` 71/141/224 — includes `cascade_conn` opens on `base_cfg`/`post_reset_cfg`; pass `busy_timeout_ms=<that cfg>.web.db_busy_timeout_ms`.
- `reconcile.py` 147/513 (the `conn = sqlite3.connect(cfg.paths.db_path)` after the `# Codex R3 Major #1` comment) and 437 (the fresh-read `fresh = sqlite3.connect(db_path)`) — pass the knob; `db_path` at 437 derives from cfg in that function.
- `app.py` 389 — `_conn = sqlite3.connect(cfg.paths.db_path)`; pass the knob.

In `swing/cli.py`:
- 149 `_apply_toml_divergence_check` → `open_connection(db_path)` (default const; cfg is the `ctx.obj["config"]` — `open_connection(db_path, busy_timeout_ms=cfg.web.db_busy_timeout_ms)` if cfg is in scope, which it is via `cfg = ctx.obj["config"]`).
- 211 `src = _sqlite3.connect(db_path)` → `src = open_connection(db_path, busy_timeout_ms=cfg.web.db_busy_timeout_ms)` (SOURCE); leave 212 `dst` (DEST).
- 227 `_probe = _sqlite3.connect(db_path)` → `open_connection(db_path, busy_timeout_ms=cfg.web.db_busy_timeout_ms)`.
- 5160 / 5201 `conn = _sqlite3.connect(str(db_path))` → `open_connection(str(db_path))` (operator `--db` arg; default const — no cfg.web here). Keep the surrounding `except _sqlite3.OperationalError` handling.

- [ ] **Step 4: Run to verify pass + the web suite green**

Run: `python -m pytest tests/web/test_live_opens_routed.py tests/web/ -q -m "not slow"`
Expected: PASS — structural test green; no web-route regression (TestClient routes still serve; `open_connection` returns a normal `sqlite3.Connection`).

- [ ] **Step 5: Run the cli suite**

Run: `python -m pytest tests/ -q -m "not slow" -k "cli and (migrate or divergence or diagnose)"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add swing/web/ swing/cli.py tests/web/test_live_opens_routed.py
git commit -m "feat(web,cli): route live-swing.db direct opens through open_connection (uniform busy_timeout)"
```

---

## Task 11: `§5` test-audit grep + WAL-sidecar cleanup confirmation

**Files:** none (verification task; fix only if the grep surfaces a real assertion)

- [ ] **Step 1: Grep the test suite for journal_mode / rollback-mode assumptions**

Run:
```bash
grep -rn "journal_mode\|PRAGMA journal\|rollback" tests/ | grep -iv "rollback()" | grep -i "journal\|delete\|truncate\|memory" || echo "no rollback-mode assertions"
```
Expected: no test asserts `journal_mode` is a rollback mode (`delete`/`truncate`/`memory`). If one exists that was passing only because some path didn't WAL-init, investigate — but per §2.2 `ensure_schema`-built DBs are ALREADY WAL today, so impact is expected to be none.

- [ ] **Step 2: Confirm tmp-DB WAL sidecar cleanup tolerance**

Run: `python -m pytest tests/data/ tests/integrations/schwab/ -q -m "not slow"`
Expected: PASS, and no leftover `*.db-wal`/`*.db-shm` warnings from `tmp_path` teardown (pytest auto-removes the tmp dir tree including sidecars). If a test opens a connection without closing it, the sidecar can linger on Windows → fix the leak (close in `finally`).

- [ ] **Step 3: Commit (only if a fix was needed)**

```bash
git add -A
git commit -m "test: WAL-mode test-suite audit (journal_mode assertions, sidecar cleanup)"
```
(If nothing changed, skip the commit and note "no fixes required" in the task log.)

---

## Task 12 (OPTIONAL, non-blocking): `.gitignore` WAL sidecar patterns

**Files:** Modify `.gitignore`

- [ ] **Step 1: Add patterns**

Append to `.gitignore`:
```
# SQLite WAL sidecars (any in-repo dev/test DB; the live DB is outside the repo)
*.db-wal
*.db-shm
*.db-journal
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore SQLite WAL sidecars (non-blocking hygiene)"
```

---

## Task 13: Full fast-suite + ruff green on the branch HEAD

**Files:** none (gate verification)

- [ ] **Step 1: Run the full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: green. **Isolate the 3 known xdist date-flakes** (per `feedback_no_false_green_claim`) — re-run any failure WITHOUT xdist (`python -m pytest <nodeid> -p no:xdist -q`) to confirm it is the pre-existing date-sensitivity, not a regression. Record the exact pass count.

- [ ] **Step 2: ruff**

Run: `ruff check swing/`
Expected: clean.

- [ ] **Step 3: Commit (only if a lint/test fix was needed)**

```bash
git add -A
git commit -m "test: arc close -- full fast suite + ruff green"
```

---

## Self-Review (run against the spec + brief; fixed inline before Codex)

**Spec coverage:**
- §4.2 centralized opener (busy_timeout-first, WAL not reaffirmed on hot path, uri=rw preserved) → Task 1, 2.
- OQ-A const + keyword + cfg knob → Task 1 (const+keyword), Task 3 (knob), Task 6/10 (knob fed at callsites).
- OQ-B route-all + classified inventory + backup-source fail-closed → inventory table above; Task 2 (core), Task 9 (backup source), Task 10 (web/cli).
- OQ-C write-pressure reduction IN V1 (serialized shared audit connection) + 3 binding contracts → mechanism section + Task 4 (lock + contracts), Task 6 (shared connection).
- §4.3 / OQ-D observability fold-in (both catch-alls, no exc_info) → Task 8.
- G2' lock-wait telemetry (after-release, slow + failed) → Task 5.
- §6 5-layer tests: config assertion (Task 2), concurrency reproduction (Task 4), production-path stress split by failure point (Task 7), observability + redaction + G2' wait (Task 5 + 8), backup-under-WAL (Task 9), §5 test-audit grep + sidecar (Task 11).
- §8 locks: NO schema (no migration task); backup integrity + gate preserved (Task 9 pins integrity); DB-outside-Drive (sidecars in ~/swing-data, unaffected); single-tx discipline (Task 4 preserves + tests); L2/L3 untouched.

**Placeholder scan:** no "TBD/handle errors/similar to Task N" — every code step shows code; scaffolding-reuse notes point to the exact existing fixtures/files to copy (Tasks 6/7/8) rather than leaving blanks.

**Type/name consistency:** `open_connection(db_path_or_uri, *, busy_timeout_ms, reaffirm_wal, uri, check_same_thread)` — same signature used in Tasks 1,2,6,9,10. `DEFAULT_BUSY_TIMEOUT_MS` const reused. `_AUDIT_WRITE_LOCK`, `_maybe_log_audit_lock_wait`, `_SLOW_ACQUIRE_WARN_THRESHOLD_S` named once and reused. `_install_pipeline_marketdata_caches` returns a 3-tuple everywhere (Task 6 Step 5 greps all callers).

**OQ-E:** the OhlcvBar bad-bar issue appears in NO task — correctly out of scope, not banked here.

---

## Execution Handoff

Plan complete. Recommended executor: **superpowers:subagent-driven-development** (fresh subagent per task, two-stage review between tasks) — the tasks are well-isolated and TDD-shaped. Inline `executing-plans` is also viable given the small blast radius.

**Gate (binding):** (1) full fast suite green on the MERGED HEAD (isolate the 3 known xdist date-flakes); (2) the production-path concurrency stress test green (Task 7); (3) **operator-witnessed FIRST instrumented live run** (post-merge, UNSEEDED normal run): confirm the ~13–22 tickers/run `database is locked` fallback collapses (Schwab becomes primary for them) AND read the G2' lock-wait telemetry to confirm the busy_timeout bump + serialized-audit-writer sufficed (if the quote path still starves at the 6 s deadline, that surfaces here and feeds the banked non-audit-writer telemetry extension).
