# SQLite Lock-Contention (WAL + busy_timeout) Arc -- Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the executing-plans implementer for the SQLite lock-contention fix. No prior conversation context.

**Mission:** Execute the LOCKed, Codex-converged plan task-by-task (TDD) into a SHIPPED, merge-ready fix for the `OperationalError: database is locked` write-lock contention that silently degrades ~13-22 tickers/run to yfinance.

**Plan (AUTHORITATIVE -- execute verbatim):** `docs/superpowers/plans/2026-06-05-sqlite-lock-contention-wal-plan.md` (1641 lines, 13 tasks = 10 implementation + 3 verification/optional; Codex-converged R1[3maj]->R2[1maj]->R3 `NO_NEW_CRITICAL_MAJOR`). Each task is a red->green->commit TDD unit with exact file:line, real code, and grounded notes. **Re-grep every cited file:line at STEP 0** (discipline #2) -- the plan was grounded on `bedd8264`; you branch from `fa4aee8d` (the plan-merge HEAD; swing/ code identical -- only the plan doc changed since). **Re-confirm R1 at STEP 0 by reading the live `swing.db` header (bytes[18,19]=2,2 = WAL already on).**

**Spec (reference only):** `docs/superpowers/specs/2026-06-05-sqlite-lock-contention-wal-design.md`.

**Context:** main HEAD at this dispatch = **`fa4aee8d`** (branch from it). ~7175 fast tests green; **schema v24 (this arc adds NO schema -- runtime PRAGMA + connection plumbing + logging only; no migration task).** NO dependency change -> standard `pip install -e ".[dev,web]"` in the worktree (no isolated venv needed -- contrast the schwabdev arc).

**Cumulative discipline (BINDING):** the **audit-service single-transaction discipline** (each write owns `BEGIN IMMEDIATE`/COMMIT/ROLLBACK; rejects caller-held tx -- the OQ-C mechanism's hard constraint); the **in-flight-row visibility contract** (the `start` row commits BEFORE the HTTP call); the WAL-already-on invariant (do NOT reaffirm WAL on the hot `connect()` path); Windows cp1252 -> ASCII only in any `print`/`click.echo`; `feedback_regression_test_arithmetic` (the plan computes each value under both paths -- preserve it). **TDD** (failing test -> SEE fail -> minimal impl -> SEE pass -> commit, per task). **ZERO `Co-Authored-By`; no `--no-verify`; final `-m` paragraph plain prose; verify `git log -1 --format='%(trailers)'` is `[]`.**

**Skill posture:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` -- the plan's recommended executor; fresh subagent per well-isolated task). After ALL tasks complete, run the **SINGLE Codex chain to convergence** (`NO_NEW_CRITICAL_MAJOR`; ~5-round cap suspended). **Codex transport (MCP DEAD):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; cat prompt.txt | codex exec -s read-only --skip-git-repo-check -'` (PATH prefix REQUIRED; codex-cli 0.135.0; pre-generate the diff on Windows; tell Codex NOT to run git). **Persist BOTH prompts AND responses** (incl. the final `NO_NEW_CRITICAL_MAJOR`) to `.copowers-findings.md`.

---

## §1 What ships (the plan's 13 tasks, in order)
1-3: the centralized `open_connection` opener (`DEFAULT_BUSY_TIMEOUT_MS=30000`, busy_timeout set FIRST, WAL NOT reaffirmed on the hot path) + route `connect`/`ensure_schema` through it + the `cfg.web.db_busy_timeout_ms` knob (no cfg import in db.py). 4: the `audit_service._AUDIT_WRITE_LOCK` wrapping ALL FOUR transaction-owning audit fns (`record_call_start`, `record_call_finish`, `link_snapshot_and_stamp_account_hash`, `link_reconciliation_run`; `in_transaction` check moved INSIDE the lock). 5: G2' lock-wait telemetry (`configured_ms` captured INSIDE the lock; the after-lock logger NEVER touches `conn`). 6: the process-wide **serialized shared audit-writer connection** (one `check_same_thread=False` conn for the pipeline hooks, opened in `_install_pipeline_marketdata_caches`, closed at the run `finally`). 7: the production-path concurrency stress test (split by failure point). 8: both ladder catch-alls log class+message (redaction-safe, no `exc_info`). 9: backup SOURCE busy_timeout (preserve fail-closed `mode=rw`). 10: route web/view-model/app/cli live-swing.db direct opens through `open_connection` (the tokenize-based open-routing test). 11: §5 test-audit grep + WAL-sidecar cleanup. 12 (OPTIONAL): `.gitignore` WAL sidecars. 13: full fast-suite + ruff green.

## §2 The OQ-C mechanism (the design-bearing core -- preserve exactly as planned)
A process-wide serialized shared audit-writer connection + the module lock. **Binding contracts the implementation MUST preserve** (the plan's tests assert these -- do not regress them): single-tx discipline; in-flight-row visibility (start commits before HTTP; lock released across the HTTP call); thread-safety (`check_same_thread=False` + the lock; `conn` is NEVER read outside audit -- verified: no `conn.execute/commit/cursor` in marketdata/ladder). The lock is process-scoped (the pipeline runs as a spawned subprocess; the 16 contending threads are inside it). Batching was REJECTED (breaks the in-flight contract) -- do not reintroduce it.

## §3 Pre-merge gate YOU deliver (in the worktree)
1. **Full fast suite green** (`python -m pytest -m "not slow" -q`). Isolate the 3 known xdist co-residency flakes (`test_ohlcv_reader_re_export_identity`, `test_read_cohort_csv_against_committed_v2trf`, `test_prices_refresh_uses_pipeline_eval_anchor`) -- confirm `-n0` if any co-resident-fails. Report the exact count (`feedback_no_false_green_claim`). 2. **Task 7 production-path concurrency stress test green.** 3. `ruff check swing/` clean. 4. Codex convergence (`.copowers-findings.md`).

## §4 Operator gate (POST-merge; you do NOT run it -- enumerate as PENDING)
**Operator-witnessed FIRST instrumented live run** (UNSEEDED normal pipeline run -- `feedback_seeded_gate_masks_default_state`): confirm the ~13-22 tickers/run `database is locked` -> yfinance fallback **collapses** (Schwab becomes the primary source for them) AND read the **G2' lock-wait telemetry**. A residual quote-path starve at the 6 s caller deadline would surface here -> feeds the banked non-audit-writer telemetry extension. You do NOT touch the operator's live DB (all tests against `tmp_path` / `ensure_schema`).

## §5 OUT OF SCOPE
The OhlcvBar bad-bar issue (its own arc, NOT banked); the non-audit-writer telemetry extension (banked first-live-run follow-on); the data-integrity arc's open items (Gate 4, close); Issue #3 metrics fix; any schema change.

## §6 Dispatch metadata
- **Subagent:** `general-purpose`, foreground, harness-default model. **Worktree:** branch `sqlite-lock-contention-arc-executing-plans` from main HEAD **`fa4aee8d`**. `python -m swing.cli`; re-check `git branch --show-current` before EACH commit (degraded-harness discipline -- if tool calls cancel mid-batch, drop to single sequential calls + re-Read before each Edit + verify each commit). **You do NOT merge** (orchestrator action at convergence). **Leave the worktree INTACT** at return (holds `.copowers-findings.md` for the orchestrator's convergence check). SINGLE Codex chain after all tasks.

## §7 Return report (mirror prior executing returns)
Final HEAD + commit list (by task); the worktree fast-suite result (exact count + any `-n0` isolation); `ruff` clean; the Codex convergent verdict (cite `.copowers-findings.md` + the verbatim `NO_NEW_CRITICAL_MAJOR`); confirm the OQ-C mechanism shipped as planned (serialized shared audit conn + `_AUDIT_WRITE_LOCK` over all 4 fns; the 3 contracts' tests green); the raw-open routing (tokenize test green); schema verdict (NONE -- v24); the operator first-live-run gate enumerated as PENDING; per-axis test-arithmetic; ZERO `Co-Authored-By`; worktree INTACT; merge-readiness.

---

*End of brief. Execute the converged 13-task plan to a shipped lock-contention fix: busy_timeout=30000 (module-const + cfg knob) + centralized `open_connection` routing ALL swing.db opens (backup fail-closed preserved) + the serialized shared audit-writer connection (`_AUDIT_WRITE_LOCK` over all 4 audit fns -- preserve single-tx + in-flight + thread-safety) + G2' lock-wait telemetry + both ladder catch-all observability + the production-path stress test. WAL already on (do NOT reaffirm on the hot path). NO schema (v24). The binding post-merge gate is the operator-witnessed first live run confirming the ~13-22 tickers/run database-locked fallback collapses.*
