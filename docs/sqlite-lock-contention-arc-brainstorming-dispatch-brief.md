# SQLite Lock-Contention (WAL) Arc -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the brainstorming implementer for the SQLite lock-contention fix. No prior conversation context.

**Mission:** Produce a LOCKed, Codex-converged brainstorm spec for eliminating the `OperationalError: database is locked` write-lock contention that silently degrades the nightly Schwab market-data fetch to yfinance for ~13-22 tickers per run.

**Skill posture:** `copowers:brainstorming`. After the spec is written, run the **SINGLE Codex chain to convergence** (`NO_NEW_CRITICAL_MAJOR`; ~5-round cap suspended -- `feedback_codex_round_limit_suspended`). **Codex transport (MCP DEAD):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; cat prompt.txt | codex exec -s read-only --skip-git-repo-check -'` (PATH prefix REQUIRED; `codex --version` -> codex-cli 0.135.0 liveness; pre-generate any diff on Windows -- the worktree `.git` is unreachable from WSL; tell Codex NOT to run git). **Persist BOTH prompts AND responses** (each round's verdict incl. the final `NO_NEW_CRITICAL_MAJOR`) to `.copowers-findings.md` for the orchestrator's independent convergence check (`feedback_implementer_persist_codex_responses`).

**Output:** spec at `docs/superpowers/specs/2026-06-05-sqlite-lock-contention-wal-design.md`.

---

## §1 The confirmed root cause (operator-witnessed live, 2026-06-05 -- do NOT re-derive; GROUND it)

The nightly pipeline OHLCV fetch degrades to yfinance for ~13-22 liquid tickers/run (SNAP, AMD, NVDA, COST, MSFT, NFLX, PLTR, AAPL, CRWD, ...). Captured exception (via an instrumented catch-all in `marketdata_ladder.py:fetch_window_via_ladder`, since reverted): **`OperationalError: database is locked`**.

Chain:
- [`swing/data/db.py:1159`](swing/data/db.py) `connect()` opens `sqlite3.connect(db_path)` with **no `PRAGMA journal_mode=WAL`** -> default rollback-journal mode, where every writer takes an **exclusive whole-DB lock**.
- The pipeline fetches OHLCV for the (post-#23-widened) detect/observe pool **concurrently**. Each `fetch_window_via_ladder` -> `get_price_history` -> `_call_endpoint` -> `audit_service.record_call_start` writes a `schwab_api_calls` row. Concurrent writers contend on the exclusive lock; the loser's INSERT exceeds the default 5 s busy timeout and raises `OperationalError: database is locked` **before** the audit row commits.
- That non-`SchwabApiError` propagates to `fetch_window_via_ladder`'s `except Exception` catch-all -> WARNING -> yfinance fallback, **with NO audit row** (the INSERT failed). This is why the failures are invisible in `schwab_api_calls` (all 49 historical production `pricehistory` ERROR rows are the *separate* OhlcvBar-invariant issue, ~2-4/run; the lock failures leave no trace).
- **This IS the pre-existing banked "Schwab market-data ladder T-C.1 wrapper erroring per-ticker -> yfinance fallback" item** (CLAUDE.md line-3). **Amplified by #23** (the aplus->aplus+watch pool widening multiplied the concurrent fetch count).

**Evidence to re-confirm at brainstorm STEP 0** (discipline #2): the `connect()` body (no WAL); the concurrent-fetch model (how the OHLCV step / `OhlcvCache` ladder fetcher spawns concurrent `get_price_history` calls and whether each gets its OWN connection -- the `database is locked` error, vs a thread-affinity `ProgrammingError`, indicates multiple connections contending, which WAL fixes); `record_call_start`'s write transaction shape.

## §2 Proposed direction (VALIDATE + refine; do not treat as final)
- **Enable WAL** (`PRAGMA journal_mode=WAL`) + a higher **`busy_timeout`** (candidate 10-30 s) on the app connection, centralized in `connect()`. WAL lets readers + one writer proceed without a whole-DB exclusive lock; write txns become short WAL appends -> contention collapses; the busy_timeout is the belt.
- **Fold in the observability fix:** `fetch_window_via_ladder`'s (and the symmetric `fetch_quote_via_ladder`'s) `except Exception` catch-all MUST log the exception class+message (redaction-safe via the existing `setLogRecordFactory`; **NOT `exc_info`** -- traceback frames can bypass the message-redaction factory). This is the fix the opaque banked issue always needed.
- **A concurrency regression test** that reproduces the lock contention pre-fix (N threads writing audit rows against a shared on-disk DB) and proves it green post-fix.

## §3 Surfaces the brainstorm MUST ground + decide (the DB connection is touched by EVERYTHING -- a naive WAL flip has wide blast radius)
- **All connection entry points:** `connect()` (db.py:1153) vs the migration runner's connection vs the `db-backup` raw `sqlite3.connect`s (db.py ~318+) vs test fixtures (`ensure_schema`). Decide WHERE WAL/busy_timeout belongs (centralize) and which connections need it.
- **Backup integrity:** `db-backup` uses the sqlite3 backup API + `PRAGMA integrity_check`; the migration **backup-gate** (`pre_version == target-1`). WAL adds `-wal`/`-shm` sidecars + checkpoint semantics -- confirm backups stay valid (the backup API is WAL-aware; a checkpoint-on-close or `wal_checkpoint(TRUNCATE)` may be needed). The `os.replace`/same-filesystem backup invariant must hold.
- **DB-outside-Drive invariant:** WAL sidecars live beside `~/swing-data/swing.db` -- OUTSIDE the Drive dir, so safe; CONFIRM no code path puts a WAL DB on the Drive.
- **Test-suite blast radius (~7175 tests):** WAL on `tmp_path` DBs (sidecar files, cleanup); confirm no test asserts `journal_mode` or breaks on `-wal`/`-shm`; the migration runner uses `executescript` with `foreign_keys=OFF` -- confirm WAL + `executescript` interplay.
- **WAL checkpoint strategy:** auto-checkpoint default (1000 pages) vs explicit; growth of the `-wal` file; checkpoint on close.
- **Scope decision:** is WAL + busy_timeout SUFFICIENT, or is additional write-pressure reduction needed (e.g. serialize/batch the audit `record_call_start`/`record_call_finish` writes during the concurrent fetch)? Prefer the minimal sufficient fix; bank the rest.
- **`.gitignore`:** `swing.db-wal`/`-shm` patterns if any test/dev DB lives in-repo (the live DB does not).

## §4 Open questions for operator triage (surface; resolve operator-paired)
- **OQ-A** `busy_timeout` value (10 s vs 30 s).
- **OQ-B** WAL scope: app `connect()` only, or also migration/backup connections?
- **OQ-C** WAL alone vs WAL + reduce concurrent write pressure (V1 scope).
- **OQ-D** fold the catch-all observability logging into THIS arc (recommend yes).
- **OQ-E** the *separate* OhlcvBar-invariant bad-bar issue (~2-4/run regular-session bars from Schwab; the data-integrity arc already makes these a clean typed->yfinance fallback): bank as accepted, or in-scope? (recommend BANK -- distinct root cause.)

## §5 Locks / invariants (propagate)
- **NO schema change** -- runtime PRAGMA only; **v24 holds**.
- DB-outside-Drive (hard invariant); backup integrity + the migration backup-gate preserved.
- The data-integrity arc's write-barrier / date-only lock-guard / typed `SchwabBarConsistencyError` / uniform topbar remain intact (this arc is orthogonal -- connection config, not market-data logic).
- L3 append-only observation lock untouched.

## §6 OUT OF SCOPE
The OhlcvBar-invariant bad-bar issue (OQ-E, likely banked); the data-integrity arc's open items (Gate 4 cassette; the arc close); Issue #3 metrics fix; Schwab Phase B/C; any schema/migration.

## §7 Dispatch metadata
- **Subagent:** `general-purpose`, foreground, harness-default model. **Worktree:** branch `sqlite-lock-contention-arc-brainstorm` from main HEAD (the orchestrator states the SHA in the inline prompt). Brainstorm writes a SPEC (no code). You MAY read live tables `mode=ro` to ground the concurrency/connection model. `python -m swing.cli`. **SINGLE Codex chain to convergence.** Leave the worktree INTACT at return (holds `.copowers-findings.md`).

## §8 Return report (mirror prior brainstorm returns)
Final HEAD + commits; the spec path + section map; Codex convergent verdict (cite `.copowers-findings.md` -- rounds + verbatim `NO_NEW_CRITICAL_MAJOR`); the grounded root cause (re-confirmed `connect()` + concurrency model); the proposed fix + the SURFACES decided (§3) + the OQs surfaced for operator triage (§4); the schema verdict (NONE); locks preserved; ZERO `Co-Authored-By`; worktree intact; writing-plans readiness.

---

*End of brief. Brainstorm the WAL/busy_timeout fix for the confirmed `database is locked` lock-contention that silently degrades ~13-22 tickers/run to yfinance (the now-root-caused banked T-C.1 issue, amplified by #23). Centralize WAL + busy_timeout in `connect()`; fold in the catch-all observability logging; add a concurrency regression test; ground the wide blast radius (backup/migration/test connections). NO schema (v24). OUTPUT: an executing-ready spec.*
