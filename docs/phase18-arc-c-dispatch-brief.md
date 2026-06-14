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

---

## 9. Writing-plans review outcome + executing-gate conditions (CHARC architecture seat, 2026-06-14 — decisions LOCKED)

Plan reviewed on disk (branch `phase18-arc-c`, `docs/superpowers/plans/2026-06-14-phase18-arc-c-yfinance-call-audit.md`, 17-round Codex-converged). The orchestrator surfaced three writing-plans decisions; **all three now resolved by both director seats** (CHARC architecture + RD measurement — RD post `…rd-18-c-writing-plans-rd-read-plan-cleared`). Operator decided #2. Executing may dispatch once the #2 delta below is applied.

**Decision #1 — enum extensions `call_type='download_intraday'` + `surface='web'`: APPROVED (both seats).** Grounded on disk: the intraday minute-bar site (`price_cache.py:206`) is a genuinely distinct shape from the daily chokepoints; `surface='web'` reflects a real caller Schwab lacks (yfinance is called from the web process; Schwab never is). #11-atomic in Task 0. Final enum sets: `call_type IN ('download_single','download_batch','download_intraday')`; `status IN ('in_flight','success','empty','error')` (the dead `rate_limited` correctly removed); `surface IN ('pipeline','cli','web')`.

**Decision #2 — FK `pipeline_run_id` ON DELETE action: LOCKED → SET NULL** (operator-decided; CHARC-recommended; RD measurement-neutral — `yfinance_calls` is an audit table the measurement chain never reads). This **REVERTS to this brief's §2 commissioned intent** ("FK to pipeline_runs, as schwab_api_calls has" = SET NULL); the plan's RESTRICT was a writing-plans divergence (Codex R13). Rationale: matches the direct mirror (`schwab_api_calls` 0018 SET NULL) + the audit-linkage convention (`temporal_log` 0022 — "detection SURVIVES run pruning"); removes the future-pruning landmine; the forever-attribution RESTRICT bought has no consumer (RD-confirmed).

> **THE PRECISE DELTA (the plan amendment / executing MUST apply — SET NULL is NOT a one-line FK flip):**
> 1. FK `pipeline_run_id REFERENCES pipeline_runs(id)` → **`ON DELETE SET NULL`** (was RESTRICT).
> 2. **DROP the SQL run-linkage CHECK** (`(surface='pipeline' AND pipeline_run_id IS NOT NULL) OR (surface IN ('cli','web') AND pipeline_run_id IS NULL)`). It is INCOMPATIBLE with SET NULL — a parent-delete NULLs a pipeline row's run_id, which would violate the CHECK.
> 3. **DROP the dataclass `__post_init__` run-linkage validator.** Else `_row_to_model` cannot round-trip a legitimately-NULLed (post-prune) pipeline row — it would raise on `YfinanceCall(surface='pipeline', pipeline_run_id=None)`. **KEEP** every other validator (enum frozensets, numeric / bool-is-int, the batch-vs-single SHAPE invariant, the non-empty-ticker invariant).
> 4. **KEEP the context-install run-linkage validation** (`set_yfinance_audit_base_context` / `yfinance_audit_scope` raises on `pipeline`+None and on `cli`/`web`+run_id). This becomes the SINGLE, correctly-placed guard for the Codex R12 unattributable-row concern — it catches the bug at the SOURCE (upstream of the insert) and never sees the post-delete state. **R12 is ADDRESSED, not abandoned** — relocated to its correct layer.
> 5. **DROP** the forward-constraint "prune yfinance_calls before pipeline_runs" note + the repo doc note (no pruning-order coupling under SET NULL).
> 6. **Tests:** remove the SQL run-linkage-CHECK-rejects test; FLIP the FK-behavior test from "parent-delete RESTRICTED" to "parent-delete SUCCEEDS + SET-NULLs the child `pipeline_run_id`, the yfinance row survives"; remove the dataclass run-linkage-`ValueError` test + ADD a positive `YfinanceCall(surface='pipeline', pipeline_run_id=None)` constructs (guards re-introduction of the validator that would break post-prune reads); reframe `test_run_linkage_check` to the CONTEXT-INSTALL layer; flip the pruning-order test to SET NULL semantics.
> 7. **Migration comment:** replace the RESTRICT-rationale block with a SET NULL note (the audit row survives run pruning, loses the link; mirrors `schwab_api_calls` 0018 + `temporal_log` 0022).
>
> Net: a SIMPLIFICATION (one fewer CHECK, one fewer dataclass validator, no landmine note; the run-linkage guard consolidated to one correct layer). It touches a Codex-converged Task 0 → run a **TARGETED Codex re-pass on the schema / model / context-install slice** (not the whole plan) to confirm convergence.

**Decision #3 — recording-architecture proportionality: CLEARED (both seats).** Every elaboration (process-global context à la `log_correlation.py`; lazy DB-free-at-import boundary; `busy_timeout=0` short-critical-section lock; wrapped post-fetch classification; the web⇄pipeline subprocess invariant) traces to a real adversarial LOCK-1 / correctness finding; RD confirms it is measurement-SAFE and the complexity BUYS measurement-path safety. **CHARC optional-simplification (flatten the base/scope/disabled state machine toward `log_correlation.py`): NOT PURSUED** — re-opening a converged design for leanness alone isn't worth the rework; banked as a V2 candidate.

**RD forward 18-D boundary (banked, no 18-C change):** `status='success'` = TRANSPORT success (raw rows returned), NOT data usability — an all-NaN-Close frame records `success` (the 18-A defect shape). `yfinance_calls` cannot catch the non-finite-OHLC class; 18-D's temporal-log non-finite scan stays the usability authority. 18-C (transport health) and 18-D (data usability) are COMPLEMENTARY. Documented in the plan (line 131); RD holds the 18-D build to it.

### Executing-gate conditions (CHARC verifies on the SHIPPED DIFF at the three-eye merge gate)
- **C1 — no measurement-chain change (LOCK 1):** records AROUND the raw `yf.download` (call / kwargs / result unchanged — kwargs-spy tests green; identical-return with/without context; the `_fetch_chunk` fallback byte-identical under a raising fetch); `busy_timeout=0` on BOTH start + finish (the fetch is never delayed); post-fetch classification wrapped (a hostile result can't replace success).
- **C2 — #11 atomic + the SET NULL delta:** the 7-point delta above applied correctly; the CHECK enums + Python frozensets + `__post_init__` + `_row_to_model` all land in ONE Task-0 commit; enum-grep clean.
- **C3 — always-on / no-environment:** no `environment` read anywhere; a row records under `environment='sandbox'`; no `_step_schwab_*` short-circuit.
- **C4 — migration 0030 discipline:** in-file `BEGIN; … COMMIT;` (#9); strict `pre_version == 29` backup gate; migrate-twice no-op; `EXPECTED_SCHEMA_VERSION == 30`; FK targets `pipeline_runs(id)`.
- **Plus the other two eyes:** RD measurement-integrity is MERGE-BLOCKING at the executing return (records-around + 0030 discipline + the transport-vs-usability boundary on the shipped diff); and the **operator-witnessed v29→v30 live-migration + backup gate** at merge (standard, as v27/v28/v29).
