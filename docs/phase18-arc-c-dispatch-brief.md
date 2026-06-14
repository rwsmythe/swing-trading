# Phase 18 Arc 18-C — yfinance call audit (commissioning brief + architecture pass)

**Authored:** 2026-06-14 by CHARC. **Roadmap:** `docs/phase18-todo.md` §18-C (deferred Arc-1c). **Tripwire: REAL — new schema (a table + migration 0030).** This is a genuine §3 crossing, so this brief carries the architecture pass (not by-construction-trivial like 18-A/B). **Cycle:** writing-plans → executing (NO brainstorm — the design is settled by mirroring `schwab_api_calls` + this pass; the one volume fork is resolved below). **Dispatch:** via a library cell (the sub-agent model is proven end-to-end); orchestrator selects the cell per the rubric (writing-plans ~opus-xhigh, executing ~opus-high) + announces.

## 1. Mandate
yfinance fetches are currently BLIND — Schwab calls are audited (`schwab_api_calls`), yfinance calls are not (confirmed on disk). Add a **`yfinance_calls` audit table + recording** mirroring the schwab pattern, so yfinance fetches are observable (timings, errors, empties, run-linkage). It exists to **feed 18-D (RD research monitor) + 18-E (tool-health monitor)** — direct data-collection observability.

## 2. Schema design (the architecture pass) — `yfinance_calls`, migration `0030` (v29 → v30)
Mirror `schwab_api_calls` (`0018:12`), adapted for yfinance. Columns:
- `call_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `ts TEXT NOT NULL` (call start)
- `call_type TEXT NOT NULL` CHECK in (`'download_single'`, `'download_batch'`) — the two chokepoints (`_yf_download_window` single; `_fetch_chunk` batch); extend the enum if the §4 enumeration finds another distinct shape (a CHECK widening = a #11 sweep).
- `ticker TEXT` (single) / `ticker_count INTEGER` (batch) — represent both shapes; a batch call is ONE row covering N tickers (this is what keeps volume modest — see §Volume).
- `response_time_ms INTEGER`
- **`status TEXT NOT NULL` CHECK in (`'in_flight'`, `'success'`, `'empty'`, `'error'`, `'rate_limited'`)** — **`empty` is FIRST-CLASS, distinct from `error`** (the F6 gotcha: yfinance returns empty for rate-limit / network / weekend, which is a transient data-collection signal the monitors must distinguish from a hard error). This is the load-bearing schema decision.
- `rows_returned INTEGER` (total rows across the call; 0 on empty)
- `error_message TEXT` (the yfinance exception string; see §Redaction)
- `pipeline_run_id INTEGER` (FK to `pipeline_runs`, as `schwab_api_calls` has — links a call to its run for the monitors)
- `surface TEXT NOT NULL` CHECK in (`'pipeline'`, `'cli'`) (yfinance is called from both)
- **NO `environment` column** — divergence from `schwab_api_calls` BY DESIGN: yfinance is the always-on, environment-agnostic fetcher (no sandbox/production domain-row gating, unlike Schwab). Adding it would imply a gating that does not exist. (Note this divergence in the migration comment.)

**Migration discipline (hard):** in-file `BEGIN; … COMMIT;` + in-file version bump (#9 — `executescript` autocommit); backup-gate STRICT equality `pre_version == 29` (the Phase-9 clause shape, NOT `<=`); migrate-twice no-op test; DB-outside-Drive invariant unchanged.

## 3. Recording — mirror `audit_service.record_call_start` / `record_call_finish`
A yfinance audit service paralleling `swing/integrations/schwab/audit_service.py`: `record_call_start` writes an `in_flight` row; `record_call_finish` sets `status`/`response_time_ms`/`rows_returned`/`error_message`, closing the row on EVERY path **including exceptions** (mirror the schwab typed-error close discipline — close the row before re-raising). The audit wraps the fetch; it MUST NOT change fetch behavior (record around the existing `yf.download`, never alter the call, its kwargs, or its result — the yfinance gotchas [`threads=False` single / the authorized `threads=True` batch] are untouched).

## 4. First task = enumerate ALL `yf.download` sites (audit-to-confirm, §5.7)
Wrap the chokepoints — `_yf_download_window` (ohlcv_archive.py:252, single) + `_fetch_chunk` (ohlcv_archive.py:483, batch) — AND enumerate every other `yf.download` call site (`grep -rn "yf.download" swing/`; the SPY benchmark fetch, `pipeline/ohlcv.py`, patterns labeling, price/ohlcv caches). Each site either routes through the audit wrapper OR is classified+documented OUT (e.g. a test-only or non-production path). No silent-skip (the #27 discipline).

## 5. LOCKS
1. **NO measurement-chain change.** This is PURELY additive observability — it observes fetches, it does not change what they return or how the measurement consumes them. `validate_bars`, the archive contents, the candidate/temporal-log shapes: untouched.
2. **#11 sweep (atomic, one task):** the `status` (and `call_type`) CHECK enum mirrored in the Python constant + the `YfinanceCall` dataclass `__post_init__` (frozenset, `Literal` is not runtime-enforced) + any repo guard — grep `swing/` for hardcoded copies. Read-path `_row_to_*` mapper widened in the same task as the write-path.
3. **Always-on recording (no sandbox gate)** — unlike `_step_schwab_*`, the yfinance audit records in ALL environments (yfinance is always-on). No production-only short-circuit.
4. **Light redaction** — yfinance calls carry NO auth token (unlike Schwab), so the heavy `setLogRecordFactory` machinery is NOT needed; defensively sanitize/truncate `error_message` (a yfinance exception could embed a URL with params — benign, but keep it tidy). Document that the light-redaction posture is deliberate (no secret surface).
5. Discriminating tests: an `empty` result records `status='empty'` (NOT error); an exception records `status='error'` + closes the row; a success records timing + rows; the row closes on every path. Regression-arithmetic both ways where it applies.

## Volume + retention (resolved, noted)
Per-call rows, but a BATCH call (`_fetch_chunk`) is ONE row for N tickers — so nightly volume is modest (~the warm's chunk count + a few single-ticker fallbacks + SPY ≈ 10–15 rows/night, the same order as `schwab_api_calls`), NOT per-ticker. Per-call granularity is therefore affordable and gives the monitors the most flexibility. A long-term prune (mirroring `swing logs cleanup` / the exports archiver) is future hygiene, NOT this arc.

## 6. Consumers + an R1 correction
- **Feeds 18-D + 18-E:** the column set (status incl. `empty`, `response_time_ms`, `error_message`, `rows_returned`, `pipeline_run_id`) serves the plausible monitor needs (error/empty rates, timing trends, run-linkage). If a monitor (when built) needs a column 18-C didn't provide, that's an additive migration THEN.
- **R1 correction (`requests` dep):** the phase18-todo guessed R1 "folds into 18-C." **It does NOT** — 18-C adds no dependency (yfinance + sqlite are already declared) and does not touch pyproject. R1 needs its own tiny dispatch or a later pyproject-touching host; it does not ride 18-C.

## 7. Gate (18-C is measurement-core — RD stays up)
Three-eye MERGE gate at executing: orchestrator QA-against-disk + CHARC (schema/migration discipline + #11 sweep + the always-on/no-environment design + the no-measurement-change lock) + **RD measurement-integrity (MERGE-BLOCKING** — confirms the audit captures what 18-D needs AND does not perturb the measurement). No-false-green merged-head re-run + ruff before close.

## 8. Return report
The ORCHESTRATOR posts to `charc, rd, operator` after its QA (the implementer reports up; never a director inbox). Itemize: the yf.download enumeration + each site's wiring/OUT, the migration (v29→v30, backup-gate, migrate-twice), the #11 sweep loci, the empty-vs-error status discriminators, the no-measurement-change lock honored on disk, Codex rounds + verdict, and the sub-agent dispatch notes.
