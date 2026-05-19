# Phase 13 T1.SB0 Gate-Fix — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 13 T1.SB0 gate-fix implementer. No prior conversation context.

**Mission:** Investigate + fix the operator-witnessed S3 visual regression surfaced post-T1.SB0 merge. CVGI chart post-Phase-13 shows ~30-40 bars with narrow window ($5.0-$5.3) + "00:00" x-axis time-of-day labels + 5K-10K volume (raw shares, not millions); pre-Phase-13 chart showed ~120 daily bars with full $1.7-$6 history + date-formatted x-axis labels + millions-scale volume. The chart-bytes byte-parity test that passed pre-merge does NOT exercise the production data-derivation path — both test paths consume identical fixture parquet — so it missed the regression.

**Brief:** `docs/phase13-t1-sb0-gate-fix-dispatch-brief.md` (this file).

**Reference plan (PRIMARY for T1.SB0 context):** `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.0 (lines 803-1043; the original T1.SB0 4-task spec).

**Reference T1.SB0 recon doc:** `docs/phase13-t1-sb0-recon.md` (the implementer's recon from the original dispatch).

**Reference T1.SB0 return report:** `docs/phase13-t1-sb0-return-report.md` (8 forward-binding lessons + 2 ACCEPT-WITH-RATIONALE banks; especially R1 M#2 V2-A bank + R3 M#1 `_yf_window_fallback` truncation fix context).

**Sequencing:** T1.SB0 SHIPPED at `418bcc8` + housekeeping at `dc0cfea`. S1 PASS via implementer; S2 PASS (pipeline runs to completion); **S3 FAIL operator-witnessed 2026-05-18 PM** — visual chart regression observed on CVGI. T2.SB1 + T3.SB1 concurrent dispatch commissioning BLOCKED until gate-fix lands. Gate-fix worktree branches from main HEAD `4a52f3a` (post-housekeeping + post-T2.SB1/T3.SB1-brief commit).

**Expected duration:** 2-3 substantive Codex rounds (4-6 tasks total: 1-2 diagnostic + 1-3 fix + 1 regression test).

---

## §0 Read first

In this order:

1. **`docs/phase13-t1-sb0-gate-fix-dispatch-brief.md`** (this file).

2. **`docs/phase13-t1-sb0-recon.md`** — T1.SB0 implementer's recon doc (355 lines). Read end-to-end. Especially §4 architecture decisions + §4.B V2-A bank (breaker non-participation) + §4 anything related to `read_or_fetch_archive` vs `fetch_daily_bars` semantic alignment.

3. **`docs/phase13-t1-sb0-return-report.md`** — T1.SB0 return report (117 lines). Especially §"ACCEPT-WITH-RATIONALE bank" (R1 M#1 OHLCV scope-clarification + R1 M#2 breaker non-participation V2-A) + §"Forward-binding lessons" (especially #3 session-anchor inequality + #4 hook fallback window-completeness + the Codex R3 Major #1 `_yf_window_fallback` fix narrative).

4. **`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.0** — original T1.SB0 plan (lines 803-1043; the 4-task spec) for context on what T1.SB0 was supposed to ship.

5. **CRITICAL — read the production code state**:
   - `swing/web/ohlcv_cache.py:get_or_fetch` (the public method introduced at T-T1.SB0.2).
   - `swing/web/ohlcv_cache.py:_fetch_bars_window` (the internal slicer; uses `read_or_fetch_archive` directly when no ladder).
   - `swing/data/ohlcv_archive.py:read_or_fetch_archive` (the underlying archive reader; consumed by both new + legacy paths).
   - `swing/pipeline/ohlcv.py:fetch_daily_bars` (the LEGACY path that pre-Phase-13 `_step_charts` used via `PriceFetcher.get`).
   - `swing/prices.py:PriceFetcher.get` (the legacy public surface that pre-Phase-13 `_step_charts` consumed).
   - `swing/pipeline/runner.py:_step_charts` (the consumer; post-T1.SB0 calls `ohlcv_cache.get_or_fetch(ticker, window_days=200)`).

6. **CLAUDE.md** at repo root — gotchas. **Especially**:
   - "OHLCV fetch scope = open-trade tickers ONLY" (existing; T1.SB0 ACCEPT-WITH-RATIONALE banked the gotcha's scope-clarification — that ACCEPT stands; no need to re-litigate).
   - "Cache + executor race" (existing; T1.SB0 preserved).
   - "yfinance regression family" (existing).
   - **"Session-anchor inequality discipline"** (NEW per T1.SB0 housekeeping commit `dc0cfea`; backward-looking `>` strict vs forward-looking `>=`).
   - **"Hook fallback window-completeness"** (NEW per T1.SB0 housekeeping commit `dc0cfea`; full archive, consumers slice).

7. **`docs/orchestrator-context.md`** "Currently in-flight work" + "Lessons captured" + "Maintenance: retention discipline".

8. **Operator-surfaced S3 evidence** (from the gate session 2026-05-18 PM):
   - CVGI-pre (5/15 run, pre-Phase-13): ~120 daily bars; x-axis dates 2025-Nov-20 to 2026-Apr-17; price range $1.7-$6; volume millions (10^6 annotation) with breakout spike ~40M.
   - CVGI (now, post-T1.SB0): ~30-40 bars visible; x-axis "00:00" time-of-day labels; price range $5.0-$5.3 (narrow consolidation only); volume 5K-10K (no 10^6 annotation; appears raw shares).
   - CTRA error in S2 stderr: "no price data found (1d 2026-05-08 -> 2026-05-19)" — yfinance gap-fill is for an **11-day window** (likely correct for a delisted ticker with stale archive needing recent days).

9. **The byte-parity test that PASSED pre-merge but missed the regression**: `tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py::test_chart_bytes_match_between_ohlcv_cache_and_legacy_price_fetcher`. Read end-to-end to understand WHY it passed despite the production-path regression.

---

## §0.5 Skill posture

- Invoke **`copowers:executing-plans`** (wraps `superpowers:subagent-driven-development` + adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`.
- Use **`superpowers:test-driven-development`** for the fix + regression test tasks.
- The diagnostic task (T-GF1) is investigation-first; commit a recon-style doc capturing root cause BEFORE writing fix code (per investigation precedent: post-Phase-12 Sub-bundle 1.5 diagnostic + 3e.12 tos-import diagnostic + Q1 reconciliation walkthrough).

---

## §1 Strategic context

### §1.1 Gate-fix scope

- **Goal**: Diagnose root cause of S3 visual regression + implement fix + ship production-path regression test that closes the byte-parity test's blind spot.
- **Branch**: `phase13-t1-sb0-gate-fix`. Worktree branches from main HEAD `4a52f3a` (current main; post-T1.SB0-housekeeping + post-T2.SB1/T3.SB1-briefs).
- **Files in scope (probable; T-GF1 diagnostic confirms exact set)**:
  - Read-only inventory: `swing/web/ohlcv_cache.py`, `swing/data/ohlcv_archive.py`, `swing/pipeline/ohlcv.py`, `swing/prices.py`, `swing/pipeline/runner.py:_step_charts`.
  - Likely modify: `swing/web/ohlcv_cache.py` (`_fetch_bars_window` — may need to invoke `fetch_daily_bars` instead of bare `read_or_fetch_archive`).
  - Likely modify or supplement: `swing/data/ohlcv_archive.py` (if a refresh-trigger needs to be added).
  - Create: `docs/phase13-t1-sb0-gate-fix-recon.md` (T-GF1 recon output).
  - Create: NEW regression test file (production-path regression; not fixture-seeded).
  - Possibly modify: `tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py` (if the fixture-seeding pattern needs revision).

### §1.2 Failure-mode hypothesis (the orchestrator's diagnosis — IMPLEMENTER VERIFIES + may revise)

**Hypothesis**: `OhlcvCache.get_or_fetch` → `_fetch_bars_window` → `read_or_fetch_archive(end_date=last_completed_session(now()), cache_dir=..., archive_history_days=...)` does **NOT trigger the weekly-refresh + gap-fill semantics** that legacy `fetch_daily_bars(ticker, lookback_days=200, as_of_date=None)` triggers.

**Pre-Phase-13 legacy chain (per pre-T1.SB0 runner.py)**:
```
_step_charts → fetcher.get(ticker, lookback_days=?, as_of_date=None)
  → PriceFetcher.get
    → fetch_daily_bars(ticker, lookback_days=?, as_of_date=None, ...)
      → [internal: weekly-refresh + gap-fill from yfinance + write-through-cache]
      → read_or_fetch_archive (after refresh)
```

**Post-T1.SB0 new chain**:
```
_step_charts → ohlcv_cache.get_or_fetch(ticker, window_days=200)
  → _fetch_bars_window(ticker, window_days=200)
    → [no ladder] → read_or_fetch_archive(end_date=last_completed_session(now()), ...)  ← SKIPS gap-fill semantic
    → slice via bars.loc[(bars.index.date >= cutoff) & (bars.index.date <= end)]
```

If the archive is stale or missing recent days, the legacy path would gap-fill via yfinance + return fresh full data; the new path returns whatever the archive contains + slices it. If the archive only contains a recent window (e.g., post-breakout consolidation period), the chart renders only that range.

The Phase 11 Sub-bundle C R1 M#5 V1 deferral comment T1.SB0 was supposed to close explicitly flagged this risk:
> "(a) a sweeping refactor of fetcher.get's weekly-refresh + archive_history_days semantics to align with the ladder's window semantics"

T1.SB0 closed the deferral by wiring the cache but did NOT reconcile those semantics. **The implementer should verify this hypothesis at T-GF1 + correct it OR identify the actual root cause.**

### §1.3 Per-task structure (proposed; refine at T-GF1 if diagnosis shifts)

- **T-GF1 — Diagnostic + recon (1-2 tasks)**:
  - Side-by-side comparison: invoke `read_or_fetch_archive(end_date=last_completed_session(now()), ...)` vs `fetch_daily_bars(ticker='CVGI', lookback_days=200, as_of_date=None)` against operator's actual CVGI archive. Capture DataFrame shapes (bar count, date range, columns, index type, volume scale).
  - Identify the divergence: (a) gap-fill behavior; (b) weekly-refresh trigger; (c) archive_history_days semantic; (d) something else.
  - Commit recon doc at `docs/phase13-t1-sb0-gate-fix-recon.md` with root cause + proposed fix shape.

- **T-GF2 — Fix (1-3 tasks; exact shape depends on T-GF1 diagnosis)**:
  - Likely shape A: `_fetch_bars_window` invokes `fetch_daily_bars(ticker, lookback_days=window_days, as_of_date=None)` instead of bare `read_or_fetch_archive` — re-routes through legacy refresh semantics for the no-ladder path.
  - Likely shape B: `read_or_fetch_archive` extended with a `refresh=True` parameter that triggers gap-fill.
  - Likely shape C: A separate refresh-trigger helper invoked before `read_or_fetch_archive` in `_fetch_bars_window`.
  - TDD per task: failing test → fix → passing test → commit (with descriptive commit message).
  - **PRESERVE T1.SB0's 2 banked ACCEPT-WITH-RATIONALE designs** — R1 M#1 OHLCV scope-clarification + R1 M#2 V2-A breaker non-participation are sound + remain. The fix is for the data-fetch semantic divergence, NOT for the gotcha-scope or breaker question.

- **T-GF3 — Production-path regression test (1 task)**:
  - **NEW test that exercises the production data-derivation path** — NOT fixture-seeded identical data.
  - Discriminating-test pattern: plant an INCOMPLETE / stale CVGI archive (e.g., archive ending 2026-04-15; today 2026-05-19) + invoke both `OhlcvCache.get_or_fetch(ticker='CVGI', window_days=200)` + `PriceFetcher.get(ticker='CVGI', lookback_days=200, as_of_date=None)` + assert both produce DataFrames covering the FULL window through "today" (gap-fill triggered on both paths).
  - This test would FAIL pre-fix (the new path returns truncated data) + PASS post-fix.
  - **Closes the byte-parity test's blind spot** — the existing byte-parity test seeds both paths with identical fixtures, bypassing this divergence.
  - Optionally: revise the existing byte-parity test to use the production-path seed instead of fixture-seed (operator-decision at gate-fix close).

### §1.4 Inherited LOCKS

- **§A.14 LOCK**: any new code preserves constant-placement discipline. Likely no new enum constants in gate-fix scope.
- **§A.15 LOCK**: no `INSERT OR REPLACE`.
- **§A.11 Schwab integration discipline**: gate-fix preserves any Schwab path discipline.
- **CLAUDE.md "Hook fallback window-completeness" gotcha (NEW per T1.SB0 housekeeping)**: any cache hook returns FULL archive; consumers slice. The fix MUST honor this discipline.
- **CLAUDE.md "Session-anchor inequality discipline" gotcha (NEW per T1.SB0 housekeeping)**: backward-looking `>` strict; forward-looking `>=`. The fix MUST honor this discipline.

### §1.5 Cross-bundle pins

T1.SB0's existing cross-bundle pin (`test_ohlcv_cache_get_or_fetch_invariant` at `tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py:203`) should still pass post-fix (the pin asserts surface signature stability, not fetch semantics).

NEW pin from gate-fix: T-GF3's production-path regression test may itself become a cross-bundle pin if it asserts production data-derivation invariants downstream sub-bundles depend on.

### §1.6 Forward-binding lessons (most-load-bearing for gate-fix)

1. **Byte-parity test as algorithmic substitute for operator-visual gate is INSUFFICIENT when test fixtures bypass production data-derivation paths** (orchestrator-side lesson surfaced at this gate-fix; CLAUDE.md gotcha addition pending post-fix housekeeping per operator decision 2026-05-18 PM).
2. **Synthetic-fixture-vs-production-emitter shape drift** (existing CLAUDE.md gotcha; Phase 12 C.D + Phase 12.5 #2 + Phase 12.5 Q2 family). The gate-fix is in the same family — fixture-seeded paths bypass production divergence.
3. **Hook fallback window-completeness** (NEW per T1.SB0 housekeeping; gate-fix MUST honor).
4. **Session-anchor inequality discipline** (NEW per T1.SB0 housekeeping; gate-fix MUST honor).
5. **Phase 11 Sub-bundle C R1 M#5 V1 deferral comment family**: when closing an explicit ACCEPT-WITH-RATIONALE V1 deferral, the orchestrator's brief MUST enumerate ALL items flagged in the deferral comment + the implementer MUST address each. T1.SB0 implementer + orchestrator both missed the explicit "weekly-refresh + archive_history_days semantics" item in the deferral comment; gate-fix closes it.

---

## §2 Executing-plans scope

### §2.1 T-GF1 acceptance criteria

- Recon doc at `docs/phase13-t1-sb0-gate-fix-recon.md` captures:
  - Side-by-side DataFrame shapes from both paths against operator's actual CVGI archive (bar count, date range, columns, index type).
  - Root cause identified (specific to the divergence; cite file:line evidence).
  - Proposed fix shape (one of A/B/C from §1.3 OR alternative if diagnosis surprises).
- Commit message: `docs(phase13): T1.SB0 gate-fix diagnostic recon — chart-window regression root cause (T-GF1)`.

### §2.2 T-GF2 acceptance criteria

- Fix implemented per T-GF1 diagnosis.
- Failing test → fix → passing test → commit per task.
- ALL existing T1.SB0 tests still PASS (shape-parity + concurrent-fetch + chart-bytes parity + yf-window-fallback-full-archive).
- New behavior matches legacy `fetch_daily_bars` semantics for the no-ladder production path.
- Commit messages: descriptive per-task (e.g., `fix(phase13): T1.SB0 gate-fix — wire _fetch_bars_window through fetch_daily_bars for refresh semantics (T-GF2.1)`).

### §2.3 T-GF3 acceptance criteria

- NEW regression test at e.g. `tests/pipeline/test_ohlcv_cache_production_path_window_completeness.py`.
- Test plants INCOMPLETE archive (e.g., archive ending N days before today) + invokes both `OhlcvCache.get_or_fetch` + `PriceFetcher.get` + asserts both return DataFrames with `bars.index[-1].date() == last_completed_session(now())` (or similar production-path full-window assertion).
- Test FAILS pre-fix; PASSES post-fix.
- Discriminating-test commentary cites:
  - The byte-parity test's blind spot (fixture-seeded; bypasses production divergence).
  - The gate-fix forward-binding lesson #1 (byte-parity-test-as-substitute is INSUFFICIENT).
- Commit message: `feat(phase13): T1.SB0 gate-fix — production-path regression test closes byte-parity-test blind spot (T-GF3)`.

### §2.4 Pre-Codex orchestrator-side review (BINDING per C.C lesson #6)

12th cumulative validation expected. Before invoking `copowers:adversarial-critic` in final round, dispatch a focused reviewer subagent with brief §1 LOCKS + §1.2 failure-mode hypothesis + §2 acceptance criteria + §1.6 forward-binding lessons as anchors. Absorb pre-Codex findings; cite as C.C lesson #6 12th cumulative validation in return report.

### §2.5 Adversarial Codex chain

2-3 substantive rounds expected. ZERO ACCEPT-WITH-RATIONALE preferred (the T1.SB0 banks already cover scope-clarification + V2-A; this gate-fix should NOT bank new ACCEPTs unless absolutely necessary).

---

## §3 OUT OF SCOPE

- **Schema changes** — gate-fix is consumer-side fetch-semantic fix; schema v19 unchanged.
- **T1.SB0's 2 banked ACCEPT-WITH-RATIONALE designs** — R1 M#1 OHLCV scope-clarification + R1 M#2 V2-A breaker non-participation are sound + remain. Do NOT re-litigate.
- **Theme 2 detector code / Theme 3 auto-fill / Theme 4 Q4 close-tracking** — gate-fix is T1.SB0-scoped only.
- **V2-A bank (breaker participation)** — still V2; do NOT add breaker to fix scope.
- **Chart-rendering code** — chart bytes are produced correctly given correct input data; the regression is in INPUT data derivation, not rendering.
- **Re-litigating plan §G.0 per-task structure** — original T1.SB0 SHIPPED + merged; gate-fix is a follow-up.

---

## §4 Binding conventions

- **Branch**: `phase13-t1-sb0-gate-fix` (worktree at `.worktrees/phase13-t1-sb0-gate-fix/` branched from main HEAD `4a52f3a`).
- **Commit messages**: per-task descriptive. Do NOT bundle tasks.
- **NO Claude co-author footer.** ~205+ commits ZERO trailer drift; DO NOT regress.
- **`python -m swing.cli`** at worktree-side gates.
- **ASCII-only on runtime CLI paths** (Windows cp1252 gotcha).
- **TDD discipline** per fix task (T-GF2.* + T-GF3).
- **Pre-Codex orchestrator-side review BINDING** per C.C lesson #6 (12th cumulative validation expected).
- **Operator-witnessed gate**: S1 inline pytest+ruff; S2 `python -m swing.cli pipeline run` against operator's production (post-fix; orchestrator-driven post-merge); S3 visual chart parity (post-fix; orchestrator-driven post-merge) — **THE PREVIOUSLY-FAILED GATE; THIS IS THE WHOLE POINT**.

---

## §5 Adversarial review watch items

1. **T-GF1 recon doc rigor** — root cause cited with file:line evidence, NOT hypothesized.
2. **Hypothesis verification** — implementer side-by-side compares against operator's REAL CVGI archive; diagnostic uses production paths, not fixture seeds.
3. **Fix preserves T1.SB0's 2 banked ACCEPT-WITH-RATIONALE designs** — R1 M#1 OHLCV scope + R1 M#2 V2-A breaker non-participation untouched.
4. **CLAUDE.md "Hook fallback window-completeness" gotcha honored** — fix returns FULL archive; consumers slice.
5. **CLAUDE.md "Session-anchor inequality discipline" gotcha honored** — backward-looking `>` strict preserved.
6. **All existing T1.SB0 tests still PASS post-fix** — shape-parity + concurrent-fetch + chart-bytes parity + yf-window-fallback-full-archive.
7. **NEW T-GF3 regression test exercises production data-derivation path** — NOT fixture-seeded; plants incomplete archive + asserts gap-fill.
8. **NEW T-GF3 regression test FAILS pre-fix** — verified by reverting fix temporarily (or by Codex review checking the test's discriminating power).
9. **Schema v19 UNCHANGED** — gate-fix is consumer-side only.
10. **`_step_charts` interface unchanged** — gate-fix is inside `OhlcvCache._fetch_bars_window`; `_step_charts` continues calling `ohlcv_cache.get_or_fetch(ticker, window_days=200)` unchanged.
11. **Per-cache locking preserved** — gate-fix doesn't introduce new race conditions.
12. **Defensive copy on store + read preserved** — Codex R3 m#1 fix from T1.SB0 stands.
13. **Phase 11 Sub-bundle C R1 M#5 V1 deferral comment items ALL addressed** — gate-fix closes (a) weekly-refresh + archive_history_days semantics (in addition to the wiring T1.SB0 already closed).
14. **Implementer self-report accuracy gate** — return report cites file:line evidence + test counts pre/post + commit SHAs verbatim.
15. **NO new CLAUDE.md gotcha additions in gate-fix housekeeping** — orchestrator decision 2026-05-18 PM: add algorithmic-substitute lesson to CLAUDE.md only after S3 PASS post-fix (deferred to post-gate-fix housekeeping commit by orchestrator).

---

## §6 Done criteria

1. Branch `phase13-t1-sb0-gate-fix` at `.worktrees/phase13-t1-sb0-gate-fix/` from main HEAD `4a52f3a`; 4-6 task-commits + Codex-fix commits + 1 return report.
2. T-GF1 recon doc at `docs/phase13-t1-sb0-gate-fix-recon.md` with root cause + file:line evidence.
3. T-GF2 fix implemented; ALL existing T1.SB0 tests still pass.
4. T-GF3 NEW production-path regression test added; FAILS pre-fix, PASSES post-fix.
5. ≥1 Codex round → NO_NEW_CRITICAL_MAJOR (2-3 rounds expected).
6. S1 inline pytest+ruff PASS.
7. Schema v19 UNCHANGED.
8. T1.SB0's 2 ACCEPT-WITH-RATIONALE designs preserved.
9. CLAUDE.md "Hook fallback window-completeness" + "Session-anchor inequality discipline" gotchas honored.
10. Return report at `docs/phase13-t1-sb0-gate-fix-return-report.md` per §7.
11. ZERO Co-Authored-By footer trailer drift across all commits.

---

## §7 Return report format

```
## Return report — Phase 13 T1.SB0 gate-fix

### Sub-bundle location
Worktree branch: `phase13-t1-sb0-gate-fix` at `.worktrees/phase13-t1-sb0-gate-fix/`
Branch base: main HEAD `4a52f3a`
Commits on branch:
- {sha} T-GF1 — diagnostic recon
- {sha} T-GF2.* — fix tasks (1-3)
- {sha} T-GF3 — production-path regression test
- (optional) {sha} Codex R<N> fix bundles
- {sha} Return report

### Root cause identified
[Citation with file:line evidence + DataFrame shape differences captured at T-GF1 recon]

### Fix shape applied
[Description of the chosen fix shape A/B/C/alternative + rationale per T-GF1 diagnosis]

### T1.SB0 banked ACCEPT-WITH-RATIONALE designs preserved
- R1 M#1 OHLCV scope-clarification: ✅ unchanged
- R1 M#2 V2-A breaker non-participation: ✅ unchanged + V2-A bank still valid

### Codex review history
- Pre-Codex (orchestrator-side review per C.C lesson #6 BINDING): {N findings absorbed; 12th cumulative validation}
- R1..RN: ... (2-3 rounds expected)
- Final verdict: NO_NEW_CRITICAL_MAJOR

### Test count pre/post
- Pre-baseline (main HEAD 4a52f3a): 4935 fast
- Post-gate-fix: {fast count} (delta: +{N}; +1-3 expected from T-GF3 regression test + any T-GF2 discriminating tests)

### Existing T1.SB0 tests still pass
- `test_ohlcv_cache_shape_parity.py`: ✅
- `test_ohlcv_cache_concurrent_fetch_no_race.py`: ✅
- `test_chart_bytes_parity_through_ohlcv_cache.py`: ✅
- `test_yf_window_fallback_returns_full_archive.py`: ✅
- `test_step_charts_ohlcv_cache_wiring.py`: ✅

### NEW T-GF3 regression test
- File: `tests/pipeline/test_ohlcv_cache_production_path_window_completeness.py` (or equivalent)
- FAILS pre-fix (verified by reverting fix temporarily OR Codex review).
- PASSES post-fix.

### S1 inline gate
- pytest: PASS at {count} fast
- ruff: PASS (0 E501 on swing/)

### Forward-binding lessons banked (for orchestrator)
- ...

### Capture-needs for orchestrator post-gate-fix housekeeping
- CLAUDE.md "byte-parity-test-as-algorithmic-substitute" gotcha addition (per operator decision 2026-05-18 PM: add only after S3 PASS post-fix).
- ...
```

---

## §8 If you get stuck

- If T-GF1 diagnosis reveals the root cause is NOT the weekly-refresh + archive_history_days semantic divergence, STOP + escalate to orchestrator + revise the fix scope at T-GF2.
- If the fix requires touching code OUTSIDE `swing/web/ohlcv_cache.py` + `swing/data/ohlcv_archive.py` + `swing/pipeline/ohlcv.py`, STOP + escalate (gate-fix scope may need widening).
- If you find yourself proposing schema changes, STOP — gate-fix is consumer-side only.
- If you find yourself proposing changes to T1.SB0's 2 banked ACCEPT-WITH-RATIONALE designs, STOP — those are sound + remain.
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly + return report.
- If the regression test at T-GF3 cannot be made to FAIL pre-fix (i.e., the test passes regardless of fix presence), the test is NOT discriminating — re-design it.

---

*End of brief. Phase 13 T1.SB0 gate-fix executing-plans dispatch — investigation-first (T-GF1 diagnostic → T-GF2 fix → T-GF3 production-path regression test); closes the S3 visual chart regression + addresses the Phase 11 Sub-bundle C R1 M#5 V1 deferral's weekly-refresh + archive_history_days semantics that T1.SB0 missed; 4-6 tasks; 2-3 Codex rounds expected. Worktree branch `phase13-t1-sb0-gate-fix` from main HEAD `4a52f3a`. T1.SB0's 2 banked ACCEPT-WITH-RATIONALE designs preserved. CLAUDE.md "byte-parity-test-algorithmic-substitute" gotcha addition deferred to post-gate-fix housekeeping (per operator decision 2026-05-18 PM).*
