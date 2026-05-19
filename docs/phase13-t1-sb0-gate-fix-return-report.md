# Return report — Phase 13 T1.SB0 gate-fix

## Sub-bundle location

Worktree branch: `phase13-t1-sb0-gate-fix` at `.worktrees/phase13-t1-sb0-gate-fix/`
Branch base: main HEAD `0fe361d` (the gate-fix dispatch brief commit, which advanced main from `4a52f3a` cited in the brief's body text)

Commits on branch (5 implementer commits = 1 recon + 2 task-impl + 2 Codex-fix doc clarifications; return report commit appended on push):

- `d440578` `docs(phase13): T1.SB0 gate-fix diagnostic recon — chart-window regression root cause (T-GF1)`
- `69da867` `feat(phase13): T1.SB0 gate-fix - fetch_window_via_ladder forwards period/frequency kwargs (T-GF2.1)`
- `6f5615d` `fix(phase13): T1.SB0 gate-fix - _bars_hook requests daily Schwab bars (T-GF2.2 + T-GF3)`
- `b329cf8` `docs(phase13): T1.SB0 gate-fix recon section 4.C clarification - Codex R1 Minor #1 (auto-recovery conditioning)`
- `5fb3d58` `docs(phase13): T1.SB0 gate-fix recon Codex R2 wording precision (minors #1 + #2)`
- *(this report commit appended on push)*

## Root cause identified

**Brief's hypothesis (`read_or_fetch_archive` weekly-refresh / `archive_history_days` semantic divergence) EMPIRICALLY FALSIFIED** by side-by-side inspection of operator's actual CVGI archive files at `~/swing-data/prices-cache/`:

| File | Rows | Unique dates | Date range | Price range | Volume range |
|---|---|---|---|---|---|
| `CVGI.parquet` (legacy daily) | **1260** | **1260** | 2021-05-12 → 2026-05-18 | $0.83 → $12.60 | 16,700 → 46,303,400 |
| `CVGI.schwab_api.parquet` (Shape A) | **2780** | **10** | 2026-05-05 → 2026-05-18 | $4.04 → $5.78 | **8 → 96,881** |

The Shape A archive is contaminated with ~278 1-minute intraday bars per date. The legacy archive is fresh + correct; `read_or_fetch_archive` is functioning normally.

**ROOT CAUSE pinpointed** (recon §2):
- `swing/integrations/schwab/marketdata_ladder.py:417-426` — `fetch_window_via_ladder` invokes `get_price_history` with NO period/frequency kwargs.
- `swing/integrations/schwab/marketdata.py:329-405` — `get_price_history` forwards all-None to schwabdev.
- `reference/schwabdev/api-calls.md:425-435` — Schwab API defaults to `periodType=day, period=10, frequencyType=minute, frequency=1` (10 days of 1-minute intraday candles) when kwargs are unspecified.
- `swing/pipeline/runner.py:383-410` — `_bars_hook` invokes `fetch_window_via_ladder(ticker, start=None, end=None, ...)` with no period/frequency kwargs.
- `swing/cli_schwab.py:1100-1111` — CLI verify path EXPLICITLY passes `period_type="month", period=1, frequency_type="daily", frequency=1` — proving the architectural intent IS for the ladder to fetch daily bars. The `_bars_hook` callsite simply forgot to mirror those kwargs.

Operator's S3 evidence aligns exactly:
- "~30-40 narrow-window bars" → mplfinance compresses 2780 candles into 10 distinct dates; visual appearance is a dense cluster.
- "x-axis '00:00' time-of-day labels" → all Shape A bars' `asof_date` is an ISO date string; `pd.to_datetime("2026-05-15")` returns `Timestamp('2026-05-15 00:00:00')`; mplfinance labels render midnight times.
- "price range $5.0-$5.3 (narrow consolidation only)" → 10 trading days ending 2026-05-18 covers exactly the post-breakout consolidation window.
- "volume 5K-10K (raw shares; no millions annotation)" → 1-minute volumes per bar are 8 to 96,881; chart's volume axis auto-scales drops the 1e6 annotation.

## Fix shape applied

**Selected fix shape D** (revises brief §1.3 A/B/C alternatives per §1.2 "implementer VERIFIES + may revise" allowance):

1. **`swing/integrations/schwab/marketdata_ladder.py`** — extend `fetch_window_via_ladder` signature with `period_type` / `period` / `frequency_type` / `frequency` kwargs (default `None`, backward-compatible); forward verbatim to `get_price_history`.
2. **`swing/pipeline/runner.py:_bars_hook`** — pass `period_type="year", period=5, frequency_type="daily", frequency=1` ("5 years of daily bars" — matches `cfg.archive.archive_history_days ≈ 1260 trading days`).
3. **`tests/pipeline/test_yf_window_fallback_returns_full_archive.py`** — absorb the new kwargs in the existing T1.SB0 R3 yf-fallback stub via `**_extra_kwargs` (additive-stub backward compat).
4. `swing/web/ohlcv_cache.py` / `swing/data/ohlcv_archive.py` / `swing/integrations/schwab/marketdata.py:get_price_history` — UNCHANGED.

**Operator's contaminated `CVGI.schwab_api.parquet` recovery** is automatic on the next pipeline run's first successful Schwab daily fetch — `write_window`'s `drop_duplicates(subset=["asof_date"], keep="last")` causes fresh daily bars to win the 10 overlapping dates + appends ~1250 prior dates. Conditional on Schwab availability; if Schwab is degraded the contamination remains on disk in `*.schwab_api.parquet` but `_bars_hook`'s return-to-cache path is UNAFFECTED (returns yfinance-fallback frame directly to OhlcvCache; chart-step renders correctly). Cross-referenced V2-F bank for an optional cleanup helper.

## T1.SB0 banked ACCEPT-WITH-RATIONALE designs preserved

- **R1 M#1 OHLCV scope-clarification** (CLAUDE.md gotcha scoped to dashboard): ✅ unchanged. Fix touches `_bars_hook` only; chart-target composition (A+ + open-trade + watchlist top-N) at `_step_charts` unchanged.
- **R1 M#2 V2-A breaker non-participation**: ✅ unchanged + V2-A bank still valid. Fix does NOT add breaker participation to the bars path.

## CLAUDE.md gotchas honored

- **"Hook fallback window-completeness"** (NEW per T1.SB0 housekeeping `dc0cfea`): ✅ preserved. Hook returns the full Schwab/yfinance archive; consumer (cache) slices to `window_days=200` unchanged.
- **"Session-anchor inequality discipline"** (NEW per T1.SB0 housekeeping `dc0cfea`): ✅ preserved. `_fetch_bars_window` strict-`>` predicate for the backward-looking `last_completed_session(now())` anchor untouched.

## Codex review history

### Pre-Codex orchestrator-side review (C.C lesson #6 BINDING — 12th cumulative validation)

Dispatched a focused reviewer subagent (general-purpose) BEFORE invoking `copowers:adversarial-critic`. Anchors: brief §1 LOCKS + §1.2 failure hypothesis + §1.6 forward-binding lessons + §2 acceptance criteria + §5 15 watch items + recon root cause + fix shape D. Asked for deviation list ≤300 words.

**Verdict: CLEAN (0 findings absorbed; 1 MINOR docstring nit — no fix needed).** This is the **12th cumulative validation** of the C.C lesson #6 pattern (Phase 12 brainstorm/writing-plans + Phase 12.5 #1/#2/#3 brainstorms + Phase 13 brainstorm + Phase 13 writing-plans + Phase 13 T1.SB0 executing-plans original + this gate-fix). Pattern continues to be durably effective.

Reviewer-confirmed checks:
- T1.SB0 ACCEPTs preserved (R1 M#1 + R1 M#2)
- New CLAUDE.md gotchas honored (Hook fallback window-completeness + Session-anchor inequality discipline)
- Other ladder callsites audited (`grep fetch_window_via_ladder(` returns ONLY `_bars_hook` at `runner.py:407`)
- `period_type='year', period=5, frequency_type='daily', frequency=1` semantically correct per `reference/schwabdev/api-calls.md:425-435` (validated against periodType/period/frequencyType allowed-value tables)
- T-GF3 test discriminating power genuine (shape-aware stub branches on `frequency_type == "daily"`; pre-fix returns minute-bars → `bars_df.index.is_unique` fails; post-fix returns daily → passes)
- Lazy-import binding correctly intercepted by monkeypatch at source module

### Codex chain summary

| Round | Critical | Major | Minor | Resolution | Verdict |
|-------|----------|-------|-------|------------|---------|
| R1 | 0 | 0 | 2 (#1 recovery-posture wording → FIX `b329cf8`; #2 T-GF3 doesn't pin write_window cleanup → ACCEPTED V1-scope) | 1 RESOLVED + 1 ACCEPTED | **NO_NEW_CRITICAL_MAJOR** |
| R2 | 0 | 0 | 2 (#1 yfinance-fallback persistence-path wording → FIX `5fb3d58`; #2 V2-F multi-signal heuristic → FIX `5fb3d58`) | 2 RESOLVED | **NO_NEW_CRITICAL_MAJOR** |
| R3 | 0 | 0 | 2 (#1 row/date-count ratio caveat for collapsed remnants → BANKED in V2-F; #2 audit-history feasibility caveat → BANKED in V2-F as "if request-parameter logging is added") | 2 BANKED V2 | **NO_NEW_CRITICAL_MAJOR** |

**Final verdict: NO_NEW_CRITICAL_MAJOR (R1 + R2 + R3 all clean).**

**ZERO Critical findings + ZERO Major findings across entire 3-round Codex chain.** All 6 findings were Minor wording-precision nits on the recon doc's recovery posture (§4.C) and V2-F bank (§4.D) — both V1-out-of-scope concerns. The actual production fix (T-GF2.1 + T-GF2.2) and discriminating regression test (T-GF3) emerged from Codex review WITHOUT a single Critical or Major finding. **Brief §2.5's "ZERO ACCEPT-WITH-RATIONALE preferred" target met — no new ACCEPT-WITH-RATIONALE banks introduced; T1.SB0's 2 prior ACCEPTs preserved untouched.**

Pattern shape: convergent zero-Major chain. R1 → R3 all NO_NEW_CRITICAL_MAJOR; minor findings tapered from 2 (R1) → 2 (R2) → 2 (R3; both V2-bank wording). Codex's V2-F minor findings reflect the depth of doc-polish review on an explicit V2 bank, not gate-fix scope concerns.

## ACCEPT-WITH-RATIONALE bank

**None for this gate-fix.** Brief §2.5 preferred zero new ACCEPT-WITH-RATIONALE banks; achieved. T1.SB0's 2 prior ACCEPTs (R1 M#1 + R1 M#2) are preserved untouched per §6 watch item #3.

## Test count pre/post

- **Pre-baseline** (main HEAD `0fe361d`): 4935 fast tests / 0 ruff E501 on `swing/` (per T1.SB0 ship state + post-housekeeping `dc0cfea` baseline).
- **Post-gate-fix** (HEAD `5fb3d58`): **4939 fast tests** / 0 ruff E501 on `swing/`. **Delta: +4 fast tests** (2 from `test_schwab_window_ladder_daily_kwargs.py` + 2 from `test_bars_hook_requests_daily_frequency.py`; within brief §7's projected +1-3 envelope).
- **Schema**: v19 UNCHANGED (gate-fix consumer-side only).
- **LOC delta**: +41 net production (`swing/integrations/schwab/marketdata_ladder.py` +20 / `swing/pipeline/runner.py` +21) + +513 test (2 new test files + 1 stub update) + +236 docs (recon doc + Codex-driven doc clarifications). All within gate-fix scope envelope.

## Existing T1.SB0 tests still pass

Verified per brief §7 enumeration:
- `tests/pipeline/test_ohlcv_cache_shape_parity.py`: ✅
- `tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py`: ✅ (1 skip = cross-bundle pin)
- `tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py`: ✅
- `tests/pipeline/test_yf_window_fallback_returns_full_archive.py`: ✅ (stub absorbed new kwargs via `**_extra_kwargs`)
- `tests/pipeline/test_step_charts_ohlcv_cache_wiring.py`: ✅
- `tests/integration/test_pipeline_marketdata_ladder_integration.py`: ✅
- `tests/integrations/test_schwab_marketdata_ladder.py`: ✅ (all 23 ladder tests + sig-pin tests)
- `tests/integrations/test_schwab_marketdata_kwarg_signatures.py`: ✅

## NEW T-GF3 regression test

- File: `tests/pipeline/test_bars_hook_requests_daily_frequency.py`
- 2 tests:
  - `test_bars_hook_invokes_ladder_with_daily_period_frequency_kwargs` — T-GF2.2 spy: monkeypatches `fetch_window_via_ladder`; asserts recorded kwargs include `period_type='year', period=5, frequency_type='daily', frequency=1`. **FAILS pre-fix** (recorded kwargs all-None).
  - `test_bars_hook_production_path_returns_daily_shaped_frame_no_duplicate_dates` — T-GF3 end-to-end: shape-aware `fetch_window_via_ladder` stub returns daily Schwab window IF caller passes `frequency_type='daily'`, else intraday-shaped window with duplicate index dates. Asserts `bars_df.index.is_unique`. **FAILS pre-fix** (stub returns intraday-shape; DataFrame has 6 rows × 2 unique dates → `is_unique=False`).
- Both PASS post-fix.
- **Closes the byte-parity test's blind spot** — the existing `test_chart_bytes_parity_through_ohlcv_cache.py` constructs a bare OhlcvCache WITHOUT installing a ladder bars fetcher, so the regression was invisible to it. T-GF3 exercises the production data-derivation path through the ladder hook plumbing.

## S1 inline gate

- pytest: **PASS at 4939 fast + 2 skipped** (cross-bundle pin + flag_classifier_integration fixture-only); zero failures.
- ruff: **PASS** ("All checks passed!"; 0 E501 on `swing/`).
- Cumulative wall-time ~108 seconds for the fast suite.

## Forward-binding lessons banked (for orchestrator)

1. **Brief hypothesis verification discipline pays off.** The brief's §1.2 hypothesis (gap-fill / weekly-refresh semantic divergence) was empirically FALSIFIED at T-GF1 by 30 seconds of inspecting operator's actual CVGI archive files. Had the implementer skipped T-GF1 + jumped straight to fix-shape A/B/C from the brief, the fix would have landed on the WRONG code path (`read_or_fetch_archive` / `fetch_daily_bars` semantics) and the regression would persist. **Pattern**: when brief offers a hypothesis with "implementer VERIFIES + may revise" allowance (§1.2), the FIRST diagnostic task (T-GF1 here) MUST do real-archive inspection / shape-comparison, NOT fix-shape selection from the brief's pre-vetted options. CLAUDE.md candidate (gate-fix dispatch pattern): "Brief-hypothesis verification is a load-bearing step, not optional. Trust the brief's STRUCTURE (LOCKS, scope, ACCEPTs preserved) but verify the HYPOTHESIS against real operator state."

2. **Schwab `client.price_history(symbol)` with no `periodType` / `frequencyType` kwargs defaults to 10 days of 1-MINUTE intraday bars (NOT daily bars).** Any caller consuming the result as daily bars (chart rendering, archive persistence, SMA computation) MUST explicitly pass `period_type="year", period=5, frequency_type="daily", frequency=1` (or equivalent month/daily combo). The mapper at `swing/integrations/schwab/mappers.py:map_price_history_to_window` bucketizes per-minute candles into `OhlcvBar.asof_date` via `.date().isoformat()` — minute-frequency responses produce ~278 bars per date (regular-hours session) with duplicate `asof_date` values. The Shape A `write_window` merge picks "last per date" via `drop_duplicates(keep='last')` — silently overwriting any prior daily-bar Shape A content with the last-minute-of-day intraday bar. **CLAUDE.md candidate (deferred to post-S3-PASS housekeeping per brief §5 watch item #15)**: "Schwab price_history minute-default footgun" — banked verbatim in recon §7 for orchestrator's post-gate-fix housekeeping commit.

3. **Byte-parity test as algorithmic substitute for operator-visual gate is INSUFFICIENT when test fixtures bypass production data-derivation paths.** The existing `test_chart_bytes_parity_through_ohlcv_cache.py` seeds BOTH paths with identical stub fixtures via `monkeypatch.setattr("swing.web.ohlcv_cache.read_or_fetch_archive", ...)`. Neither path exercises the ladder hook — the test by construction asserts shape parity within the no-ladder branch ONLY. The regression was production-only (Schwab ladder enabled) and the byte-parity invariant held in test but failed in production. **CLAUDE.md candidate (deferred to post-S3-PASS housekeeping per brief §5 watch item #15)**: brief §1.6 forward-binding lesson #1 captured; banked verbatim for orchestrator's post-gate-fix housekeeping commit.

4. **Pre-Codex orchestrator-side review = 12th cumulative validation, durably effective (C.C lesson #6 CARRY).** This is now the 12th cumulative validation of the pattern. Returned CLEAN with 1 advisory MINOR docstring nit (no fix needed). Codex R1 likewise opened NO_NEW_CRITICAL_MAJOR — the pre-Codex review correctly anticipated reviewer concerns. **Pattern is DURABLE; continue applying at every executing-plans + gate-fix dispatch.**

5. **Brief-vs-implementation hypothesis divergence is a feature, not a bug, when "implementer VERIFIES" is in scope.** The brief offered an articulated hypothesis (gap-fill / archive-history semantics) + 3 fix shapes (A/B/C) + an "implementer VERIFIES + may revise" allowance. T-GF1 falsified the hypothesis with empirical evidence; T-GF2 selected fix shape D (alternative). The brief's STRUCTURE held perfectly — same scope, same LOCKS, same ACCEPTs preserved, same regression test discipline. Only the hypothesis turned out to be wrong. **Pattern**: orchestrator-issued briefs SHOULD include articulated hypotheses + fix-shape options + verify-and-revise allowance; implementer SHOULD treat them as starting points, not commitments.

6. **`grep fetch_window_via_ladder(` audit is reusable for any "single-callsite fix" verification.** The pre-Codex reviewer + Codex both verified that `_bars_hook` is the ONLY production callsite of `fetch_window_via_ladder` (`swing/cli_schwab.py` uses `get_price_history` directly, not via the ladder). Closing the ladder-side bug at the single callsite + extending the wrapper additively is sufficient. **Pattern**: any "wrapper-extension + single-callsite fix" should include the grep audit as an explicit pre-Codex watch item ("all callsites of X enumerated; only callsite Y needs the new behavior").

## Capture-needs for orchestrator post-gate-fix housekeeping

1. **CLAUDE.md "Schwab price_history minute-default footgun" gotcha addition** (per recon §7 banked text + brief §5 watch item #15 operator-decision): add the "Schwab `client.price_history(symbol)` with no `periodType` / `frequencyType` kwargs defaults to 10 days of 1-MINUTE intraday bars" gotcha verbatim. Add to the existing Schwab/schwabdev gotcha family in CLAUDE.md.
2. **CLAUDE.md "Byte-parity test as algorithmic substitute is INSUFFICIENT when test fixtures bypass production data-derivation paths" gotcha addition** (per brief §1.6 forward-binding lesson #1 + operator decision 2026-05-18 PM): add the algorithmic-substitute-vs-operator-visual-gate gotcha verbatim. Part of the existing "Synthetic-fixture-vs-production-emitter shape drift" gotcha family.
3. **V2-F bank (Shape A archive backfill cleanup)** — multi-signal contamination detector + cleanup helper. Tracked at recon §4.D + clarified at R2 wording fix. Optional; operator-friendly UX for sustained-Schwab-outage scenarios.
4. **Cross-bundle pin** from T1.SB0 (`test_ohlcv_cache_get_or_fetch_invariant` at `tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py:203`) UN-SKIP schedule unchanged: still T2.SB2 + T2.SB3 + T3.SB3 per plan §H.3.
5. **T2.SB1 ∥ T3.SB1 concurrent dispatch UNBLOCK condition**: now contingent on post-merge S2 + S3 operator-paired gate PASS (orchestrator-driven). S2 = `python -m swing.cli pipeline run` against operator's production; S3 = visual chart parity vs pre-Phase-13 baseline.

## Outstanding capture-needs that DEFER

- **V2-A bank** (carried forward from T1.SB0): breaker participation for the bars path. Unify cache health across bundle + bars surfaces. Defer until operator surfaces meaningful Schwab/yfinance outage failure modes that aren't well-handled by per-ticker `fetcher_failed`.
- **V2-B bank** (carried forward from T1.SB0): per-key in-flight dedup. Defer until profiling demonstrates pain.
- **V2-C bank** (carried forward from T1.SB0): async `get_or_fetch` variant via executor. Defer until detector batch sizes grow.
- **V2-D bank** (NEW from gate-fix recon §4.D): defensive kwarg validation at `get_price_history` — raise on `(start_dt=None, end_dt=None, period_type=None, period=None)` combination since this triggers Schwab's minute-default footgun. Skipped in V1 to keep gate-fix surgical.
- **V2-E bank** (NEW from gate-fix recon §4.D): mapper-side duplicate-`asof_date` rejection — `map_price_history_to_window` could raise `SchwabSchemaParityError` when it observes >1 candle for the same `asof_date`. Defense-in-depth; skipped in V1.
- **V2-F bank** (NEW from gate-fix recon §4.D + clarified at Codex R2/R3): Shape A archive backfill cleanup with multi-signal heuristic (duplicate asof_date / row-date-count ratio / volume-scale anomaly / optional audit-history if request-parameter logging is added). Operator-friendly UX for sustained-Schwab-outage scenarios.
- **S2 + S3 operator-witnessed gates** (production pipeline run + visual chart parity vs pre-Phase-13 baseline): orchestrator drives post-merge.

## Co-Authored-By footer trailer audit

`git log 0fe361d..HEAD --pretty=format:"%H %(trailers:key=Co-Authored-By)"` returned 5 SHAs each with an empty trailers field. **ZERO `Co-Authored-By` footer trailer drift** across all gate-fix commits. Cumulative project streak (~205+ commits cumulative; +5 from this gate-fix; the return report commit will be the 6th) preserved.

---

*End of return report. Phase 13 T1.SB0 gate-fix SHIPPED on worktree branch `phase13-t1-sb0-gate-fix`. 1 recon + 2 task-impl + 2 Codex-fix doc clarifications + 1 return report = 6 implementer commits. 3 Codex rounds; ZERO Critical findings + ZERO Major findings entire chain (brief §2.5 zero-ACCEPT target met); 6 minor wording-precision findings across the chain (2 RESOLVED via doc clarification commits, 4 V2-bank wording or ACCEPTED-V1-scope); 12th cumulative validation of C.C lesson #6 pre-Codex review pattern (CLEAN). Orchestrator drives the S2 + S3 operator-witnessed gates + integration merge + post-merge housekeeping. After post-S3-PASS housekeeping (including the deferred CLAUDE.md "Schwab minute-default footgun" + "byte-parity-test-algorithmic-substitute" gotcha additions per operator decision 2026-05-18 PM), T2.SB1 ∥ T3.SB1 concurrent dispatch per OQ-12 Option E proceeds.*
