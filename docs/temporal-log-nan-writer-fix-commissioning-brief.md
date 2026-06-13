# Temporal-log NaN-writer fix — RD→CHARC commissioning brief

**Author:** Research Director (RD). **Routes to:** CHARC (architecture pass per charter §1 — crosses a §3 tripwire: the temporal-log writer in `swing/pipeline`, possibly `swing/data`; the measurement chain).
**Date:** 2026-06-13. **Priority:** HIGH (operator-stated). **Candidate placement:** Phase 18 (CHARC/operator decide).
**Status:** demand/problem statement + locks + verification mandates + open design questions. The converged spec is allowed to be smarter than this brief (charter directive #10); the brief's job is a correct PROBLEM + locks + verification, not a prescribed solution.

## §0 Read first
- The 2026-06-13 RD data-collection audit (charter §7 once logged) — the evidence base for this brief.
- CLAUDE.md §Gotchas → "yfinance / market-data" → the **Arc-8 trailing-NaN-Close** entry (F6-addendum). This defect is the SAME class on a SECOND, unguarded write path.
- `research/harness/shadow_expectancy/validate.py:32` (`validate_bars`) + `run.py:147` — the engine gate that makes this an exclusion, not a corruption.

## §1 Strategic context (compressed)
The shadow-expectancy measurement is the centerpiece instrument and it is **sample-starved** (4 priced unique names; decision gate N≥30). A single data-quality event is currently removing **~30% of the attributed broad-watch population** from pricing eligibility, it **recurs**, and it was **invisible on every operator-facing surface**. Fixing the writer now — before the log matures and before more sessions accrue — is the "catch problems early to minimize lost time" the operator asked for. This is a correctness defect in the instrument, not a feature; it justifies deviating from the standing stop-engineering posture (watch-standard §6.4, written justification recorded in the audit).

## §2 The defect (problem statement + evidence)
**Root cause (confirmed in code):** `build_ohlc_today_json` (`swing/pipeline/temporal_metadata.py:149`) is the temporal-log construction barrier. It guards **completed-session (date ≤ cutoff) + key-presence + provider-domain** — but **NOT value finiteness**. A completed *past* session whose yfinance adjusted `Close` returns `NaN` (the Arc-8 trailing-ragged artifact: O/H/L/V present, Close=NaN) passes all three gates, and `json.dumps` writes `"close": NaN` into the **immutable, append-only** log.

**Evidence (live DB, read-only, 2026-06-13):**
- **103 forward observations across 19 tickers** (ALGM, BULZ, CADL, CIFR, COHU, CVGI, EWTX, GFS, GPRK, HIMX, IRDM, LPTH, NOK, POWI, SHLS, SPYU, TAN, TSMX, UCTT), **all** for the **2026-06-10** session, **all** with `Close=NaN`, O/H/L/V present, `provider=yfinance`. Bounded: a full scan of all 1,287 forward observations found non-finite OHLC ONLY on 06-10 (a single fetch-timing event so far).
- Every one is an **interior** hole (bracketed by valid 06-09 and 06-11 closes). The log does not backfill → **permanent**.
- The **Arc-8 `_trim_trailing_ragged` barrier exists only in `swing/data/ohlcv_archive.py`** (lines 202/256/689). It was never mirrored onto this second write path. Two-path divergence (the recurring "parallel-archive / synthetic-vs-production" gotcha family).

**Consequence — sample attrition, NOT corruption:** the engine's `validate_bars` correctly rejects any chain containing a non-finite bar → those signals are routed `excluded → invalid_ohlc` BEFORE the trigger test (`run.py:147`), so **no R is ever poisoned** (the engine is robust; the 4 priced names are clean and hand-verified). The cost is throughput: from the manifests, `invalid_ohlc` went `06-10:0 → 06-11:22 → stable 22–23`, i.e. **23 of 77 attributed signals (30%) permanently excluded** in a starved measurement.

**Observability gap (secondary defect):** `invalid_ohlc` and the other excluded reasons appear **only in `manifest.json`** — not in `summary.md`, not in `scripts/weekly_glance.py`. The operator-facing read (`trigger 10/33`, `unattributed=0`) looked healthy while a third of the population silently dropped out.

## §3 Required outcome + LOCKS
**Outcome:** non-finite OHLC must never enter the temporal log. The fix mirrors Arc-8 semantics at this second write path; prefer a **single shared trailing-ragged helper** (or shared finiteness predicate) so the two paths cannot re-diverge.

**LOCKS (do not violate):**
1. **Do NOT weaken `validate_bars`** to accept NaN. The engine's honest-rejection gate is correct and stays; it is the belt to the writer's suspenders.
2. **Preserve** the existing completed-session / key-presence / provider guards in `build_ohlc_today_json` (add finiteness; don't remove what's there).
3. **Append-only / immutable-log discipline holds.** Any repair of the 103 existing rows is a SEPARATE, governed decision (§4.2) — not a silent in-place mutation.
4. **Interior-valid bars preserved.** The Phase-15 bad-bar-accept posture for HISTORICAL interior bars is unchanged; this is specifically about non-finite OHLC at the write barrier (and trailing-ragged), not about discarding legitimate interior data.
5. **Read/measurement chain otherwise untouched** (no schema change unless §4.2 backfill is chosen → then a migration, CHARC-gated).

## §4 Open design questions (for the brainstorm/spec + CHARC)
1. **Writer behavior on a non-finite bar.** Skip-with-warning (mirror Arc-8 "never persist bad data; leave stale; retry next call") vs reject-and-raise. **RD lean: skip + a `warnings_json` line** (auditable; also closes the observability gap). Confirm whether a skipped session can be backfilled on a later run or becomes a one-session hole (the engine tolerates a hole; it does not tolerate a NaN).
2. **The 103 already-poisoned rows.** Leave (they age out as clean detections accrue; engine handles honestly) vs a **one-time governed backfill** from the Arc-8-protected `ohlcv_archive` (recovers 19 tickers' pricing eligibility; mutates the "immutable" log → a governance call that routes through RD). Given the starvation, **cost the backfill** even if the decision is to defer it.
3. **Surface the excluded-reason breakdown** (`invalid_ohlc`/`insufficient_forward_depth`/`missing_observations`) in `summary.md` (and feed the health monitor — see the companion brief). May fold into this arc or the monitor arc; CHARC sequences.

## §5 Verification mandates
- **Build the failing test from the REAL 06-10 shape**: a completed-session bar (`date ≤ cutoff`), keys present, `provider="yfinance"`, `Close=NaN`, O/H/L/V finite. Current `build_ohlc_today_json` MUST be shown to accept it (red) and the fixed barrier MUST skip/reject it (green) — compute the assertion under both paths (memory `feedback_regression_test_arithmetic`).
- **Discriminators:** a fully-valid completed bar still records (no over-eager rejection); an interior-valid bar is preserved (the all-NaN F6 case and the single-field-NaN trailing case both covered; the Volume-only-NaN exemption from Arc-8 reconciled).
- **If backfill is chosen:** verify the engine re-prices the recovered tickers, and verify NO look-ahead is introduced by the repair (the existing `observation_date ≥ data_asof_date` invariant holds).

## §6 Routing
CHARC architecture pass (tripwire: temporal-log writer; `swing/pipeline` + possibly `swing/data`/migration if backfill) → copowers brainstorm → writing-plans → executing-plans, Codex to convergence → RD QAs the return → operator gate only if live data is mutated (the §4.2 backfill). Land independently of the companion health-monitor arc.
