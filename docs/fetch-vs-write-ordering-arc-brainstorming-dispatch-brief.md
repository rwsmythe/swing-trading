# Fetch-vs-Write-Ordering Fix Arc -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the brainstorming implementer for the OHLCV-fetch-inside-held-`fenced_write` deadlock fix. No prior conversation context.

**Mission:** Produce a LOCKed, Codex-converged brainstorm spec that eliminates the SQLite write-lock deadlock where the nightly pipeline holds a `lease.fenced_write()` write transaction open ACROSS a network OHLCV fetch, so the fetch's audit-row writes (on a separate connection) deadlock on the held lock and time out -> silent yfinance degrade for ~13-22 tickers/run.

**Skill posture:** `copowers:brainstorming`. After the spec is written, run the **SINGLE Codex chain to convergence** (`NO_NEW_CRITICAL_MAJOR`; ~5-round cap suspended -- `feedback_codex_round_limit_suspended`). **Codex transport (MCP DEAD):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; cat prompt.txt | codex exec -s read-only --skip-git-repo-check -'` (PATH prefix REQUIRED; codex-cli 0.135.0; pre-generate any diff on Windows -- worktree `.git` unreachable from WSL; tell Codex NOT to run git). **Persist BOTH prompts AND responses** (incl. the final `NO_NEW_CRITICAL_MAJOR`) to `.copowers-findings.md`.

**Output:** spec at `docs/superpowers/specs/2026-06-06-fetch-vs-write-ordering-design.md`.

---

## §1 The CONFIRMED root cause (operator-witnessed Run 92 2026-06-06 + orchestrator-verified -- do NOT re-derive; GROUND + ENUMERATE it)
The SQLite-lock-contention arc (busy_timeout=30000 + serialized audit writer, merged `ffb5fdc6`) did NOT collapse the `database is locked` fallback at the live gate. Its G2' telemetry revealed the TRUE cause:
```
audit record_call_start: BEGIN IMMEDIATE FAILED (database is locked) after ~33s (busy_timeout=30000ms)
```
A writer holds the SQLite write lock for 30+s during the market-data fetch. **CONFIRMED locus:** `_step_pattern_detect` Pass-2 opens `with lease.fenced_write() as conn:` at **runner.py:1898** and, INSIDE that held write transaction, calls `ohlcv_cache.get_or_fetch(...)` at **runner.py:1994** (the exemplar-bar fetch in the `for ex_row in exemplar_rows:` loop). `get_or_fetch` -> the ladder hook -> `get_price_history(conn=audit_conn)` -> `record_call_start` does `BEGIN IMMEDIATE` on the SEPARATE shared `audit_conn` -> deadlocks on the lock held by the `fenced_write` conn -> waits `busy_timeout` -> fails -> yfinance fallback. The Run-92 failures were CANDIDATE tickers (AAPL/NVDA/SNAP/...), so the SAME pattern almost certainly exists in **`_step_charts`** (runner.py:2712) and/or **`_step_pattern_observe`** (runner.py:2576) for candidate-window fetches. busy_timeout + the serialized audit writer CANNOT fix a held lock owned by a different connection.

**STEP-0 audit (the brainstorm's core deliverable):** enumerate EVERY `lease.fenced_write()` block in `runner.py` (grep-confirmed instances near 736, 1245, 1274, 1316, 1422, 1541, 1654, 1898, 2269, + any in charts/observe) and classify each: does it contain an **audit-writing fetch** inside the held transaction (`ohlcv_cache.get_or_fetch`, `price_cache.get`, or any ladder/`get_price_history`/`get_quotes_batch` call)? Produce the COMPLETE locus list -- a missed locus = a residual deadlock.

## §2 Proposed direction (VALIDATE + refine; not final)
**Pre-fetch OHLCV bars BEFORE opening `fenced_write`; keep only the fast SQLite reads inside the transaction.** For the detect Pass-2 exemplar locus: the exemplar ROW read (`list_exemplars(conn)`) is deliberately in-tx for corpus consistency (runner.py:1969 comment) -- KEEP the row read in-tx, but FETCH the exemplar bars (network) BEFORE/OUTSIDE the `fenced_write` (or reuse a pre-fetched cache). Same shape for charts/observe: fetch all needed bars first, then open the write transaction only around the persist. The audit writes then happen with NO competing held lock.

## §3 Surfaces the brainstorm MUST ground + decide
- **The complete locus list** (§1 audit) -- detect Pass-2 (1898/1994) + charts + observe + any other.
- **Per-locus reorder design:** what must stay in-tx (consistency-critical reads: the canonical_existing re-read @1920, the exemplar corpus row read @1977) vs what moves out (the network bar fetches). Preserve the Pass-2 reconcile-before-serialize architecture + the in-tx corpus-consistency contract.
- **#5 no-re-fetch / L2 LOCK:** detect Pass-1 already fetches candidate bars into `bars_by_ticker` (runner.py:1712/1740) -- reuse them in Pass-2 (do NOT re-fetch). The exemplar bars are NOT in bars_by_ticker (different tickers) -> pre-fetch them once before the write tx.
- **#28/#29 exemplar OHLCV depth/presence:** exemplars are outside the candidate universe; their bars need the historical-depth pre-fetch (period="max" / window from MIN(end_date)-200d) -- ensure the moved-out fetch preserves this.
- **The just-merged lock arc stays:** busy_timeout + the serialized audit writer + the G2' telemetry + the catch-all observability are correct keepers; this arc removes the held-lock so the telemetry will show the deadlocks collapse. **The stopgap `[web] db_busy_timeout_ms = 5000` in `swing.config.toml` MUST be reverted to 30000 (or the key deleted) as part of THIS arc's completion** (once the deadlock is gone, 30s is the correct safe value).
- **Lease semantics:** the reorder must not violate the lease-fencing contract (the write must still happen inside `fenced_write` with the in-tx lease check); only the FETCH moves out.

## §4 Open questions for operator triage (surface; resolve operator-paired)
- **OQ-A** pre-fetch strategy: fetch each locus's bars just-before its own write tx, vs one up-front bulk pre-fetch of all detect/charts/observe + exemplar bars (memory + Schwab-quota implications; the #23-widened pool is large).
- **OQ-B** stopgap-revert timing: revert `db_busy_timeout_ms` to 30000 IN this arc's executing phase (recommend yes -- the deadlock is gone so 30s is safe) vs after the live gate confirms.
- **OQ-C** the exemplar in-tx corpus-consistency contract -- confirm moving the bar fetch out (keeping the row read in) preserves spec section 5.7 retrieval semantics.

## §5 Locks / invariants (propagate)
NO schema (v24); DB-outside-Drive; the lease-fencing contract (write stays in `fenced_write` + in-tx lease check); the audit single-tx discipline; #5 no-re-fetch / L2 LOCK; #27 silent-skip-audit (any new early-return emits a warnings_json entry); #28/#29 exemplar depth; the data-integrity arc barriers + the lock-contention arc keepers intact.

## §6 OUT OF SCOPE
The OhlcvBar bad-bar issue (its own queued arc, NOT banked); the banked non-audit-writer telemetry extension (revisit after this fix if any residual contention shows); Issue #3 metrics fix; any schema change.

## §7 Dispatch metadata
- **Subagent:** `general-purpose`, foreground, harness-default model. **Worktree:** branch `fetch-vs-write-ordering-arc-brainstorm` from main HEAD (orchestrator states the SHA in the inline prompt). Brainstorm writes a SPEC (no code). You MAY read live tables `mode=ro`. SINGLE Codex chain to convergence. Leave the worktree INTACT.

## §8 Return report (mirror prior brainstorm returns)
Final HEAD + commits; spec path + section map; Codex convergent verdict (cite `.copowers-findings.md`); **the COMPLETE fenced_write-wrapping-a-fetch locus list** (the core deliverable) + the per-locus reorder design; the OQs surfaced; the stopgap-revert plan; schema verdict (NONE); locks preserved; ZERO `Co-Authored-By`; worktree intact; writing-plans readiness.

---

*End of brief. Brainstorm the fetch-vs-write-ordering fix for the CONFIRMED `database is locked` deadlock (OHLCV fetch inside a held `lease.fenced_write` -- runner.py:1898/1994 detect Pass-2 + the charts/observe candidate-fetch loci). Enumerate EVERY locus; design the pre-fetch-before-write reorder preserving the in-tx consistency reads + #5/#28/#29; plan to revert the busy_timeout stopgap. NO schema. OUTPUT: an executing-ready spec.*
