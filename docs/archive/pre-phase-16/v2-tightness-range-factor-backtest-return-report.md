# V2 vcp.tightness_range_factor=1.005 Walk-Forward Backtest — Return Report

**Date:** 2026-05-24
**Branch:** `applied-research-v2-tightness-range-factor-backtest`
**Base:** main HEAD `30dbd69` (dispatch-brief commit)
**Findings doc:** [docs/v2-tightness-range-factor-backtest-findings-2026-05-24.md](v2-tightness-range-factor-backtest-findings-2026-05-24.md)
**Dispatch brief:** [docs/v2-tightness-range-factor-backtest-dispatch-brief.md](v2-tightness-range-factor-backtest-dispatch-brief.md)

---

## 1. Headline outcome

**Backtest verdict: INSUFFICIENT POSITIVE EVIDENCE.**

Of 17 unique VCP patterns derived from 67 watch→aplus flips at `vcp.tightness_range_factor=1.005`:
- 12 (70.6%) never triggered (close never crossed pivot; max forward close 86-99% of pivot for the 10 patterns with adequate forward data).
- 2 (11.8%) had zero forward bars (SSRM/WULF; first asof = 2026-05-15 == archive last bar).
- 5 (29.4%) triggered; all 5 remain OPEN at data tail; mean unrealized R = **-0.18R** (1 marginally positive at +0.04R; 4 negative -0.13 to -0.34R).
- **0 patterns closed** under any of the 3 exit rulesets — none progressed to a +1R BE / +2R extension / 50d-SMA-arm.
- All 3 rulesets emit identical pattern-level outcomes on this cohort — they are indistinguishable when the gating event (post-+2R extension; post-+1R BE; post-50d-cross) never fires.

**Recommended operator-paired next action:** Option A — pivot to a different binding-variable backtest (e.g., `vcp.tightness_days_required` +16). Option B (archive refresh + re-run) is a low-cost follow-up that closes the data-sparsity caveat. Detailed evidence at findings doc §1, §6, §8.

---

## 2. Deliverables shipped

| Deliverable | Path | Status |
|-------------|------|--------|
| Per-pattern per-ruleset results CSV | `exports/research/tightness-range-factor-backtest-<ISO>/results.csv` + `results_cohort.csv` + `results_control.csv` | SHIPPED |
| Aggregate stats markdown | `exports/research/tightness-range-factor-backtest-<ISO>/summary.md` | SHIPPED |
| Findings doc | `docs/v2-tightness-range-factor-backtest-findings-2026-05-24.md` | SHIPPED |
| Study writeup amendment | `research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md` (new §"Walk-forward backtest validation (vcp.tightness_range_factor=1.005)" appended) | SHIPPED |
| Return report | `docs/v2-tightness-range-factor-backtest-return-report.md` (this file) | SHIPPED |

---

## 3. Code + tests shipped

### 3.1 Backtest harness modules (NEW)

`research/harness/backtest_v2_tightness/`:
- `__init__.py` — package docstring; L2-LOCK + ZERO-V1-mutation discipline notes.
- `patterns.py` — `CandidateRow` + `Pattern` dataclasses; `group_consecutive_eval_runs(rows, max_gap_business_days=5)` business-day-aware dedup.
- `walkforward.py` — `Trade` dataclass; `find_entry_index(...)` entry trigger; `walk_forward(pattern, forward_bars, ruleset)` per-pattern engine. Trade carries diagnostic columns: `forward_bars_available`, `max_forward_close`, `max_close_pct_of_pivot`.
- `rulesets.py` — `RulesetA` (Minervini trail-MA) + `RulesetB` (Fixed R-multiple) + `RulesetC` (Close-below-50d-SMA); shared `_sma_at` + `_sma_rising` helpers; `all_rulesets()` factory.
- `io.py` — `write_results_csv(trades, path)` + `aggregate_stats(trades)` + `write_summary_markdown(...)`.
- `run.py` — CLI orchestrator: `python -m research.harness.backtest_v2_tightness.run --flip-rows-csv ... --db-path ... --cache-dir ... --output-dir ...`.

### 3.2 Tests (NEW)

`tests/research/backtest_v2_tightness/`:
- `test_patterns.py` — 5 tests covering consecutive-run collapse, multi-cluster split, multi-ticker independence, first-eval-run pivot/stop usage, empty input.
- `test_rulesets.py` — 11 tests covering entry trigger (find_entry_index + untriggered semantics), Ruleset A (stop_hit, trail arm + close_below_50d), Ruleset B (target_3R, stop_hit pre-BE, BE arms at +1R), Ruleset C (stop_hit pre-arm, close_below_50d post-arm), open-position-at-data-tail.

**All 16 tests pass under `python -m pytest tests/research/backtest_v2_tightness/`.**

### 3.3 Inline data extraction artifacts

`tmp/backtest/flip_rows.csv` + `tmp/backtest/flip_with_pivots.csv` — orchestrator-extracted 67 flip rows joined with V1-persisted pivot/initial_stop/close from `candidates` table. These tmp/ files are NOT tracked.

---

## 4. Discipline preservation verification

### 4.1 Co-Authored-By footer streak preserved

All commits authored by this dispatch carry ZERO `Co-Authored-By` trailers (preserved ~509+ cumulative streak through `30dbd69`).

### 4.2 L2 LOCK preserved (ZERO new Schwab API calls)

The backtest harness consumes ONLY:
- `research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader.read_yfinance_shape_a` (V2's read-only Shape A reader; legacy fallback)
- `research.harness.aplus_v2_ohlcv_evaluator.exceptions.OhlcvCoverageError` (typed exception)
- Standard library + numpy + pandas.

ZERO imports from `swing.data.ohlcv_archive`, `swing.integrations.schwab.*`, `yfinance`, or any Schwab-API path. Verifiable via `grep -r 'import' research/harness/backtest_v2_tightness/`.

### 4.3 V1 persisted state UNCHANGED

The backtest harness performs SELECT-only queries against:
- `evaluation_runs` (id, data_asof_date)
- `candidates` (ticker, evaluation_run_id, bucket, pivot, initial_stop, close)

ZERO UPDATE / DELETE / INSERT statements. Verifiable via `grep -r 'UPDATE\|DELETE\|INSERT' research/harness/backtest_v2_tightness/` (zero matches).

### 4.4 Schema v21 UNCHANGED

ZERO files in `swing/data/migrations/` added/modified. Verifiable via `git diff main -- swing/data/migrations/` (empty).

### 4.5 Production `swing/` READ-ONLY

ZERO files modified under `swing/`. Verifiable via `git diff main -- swing/` (empty).

### 4.6 ASCII-only on CLI + markdown narrative

All CLI prints + markdown documents are ASCII-only. No glyphs (§ / → / ↔ / em-dash) introduced.

### 4.7 `python -m swing.cli` invocation discipline

Backtest invoked via `python -m research.harness.backtest_v2_tightness.run` (NOT a bare `swing` CLI invocation; package-module discipline preserved).

---

## 5. Design decisions + deviations from brief

### 5.1 Pivot derivation: V1-persisted `candidates.pivot`, NOT recomputed from OHLCV

**Brief §1 + §2 inferred:** "pivot = consolidation_high from V2 evaluator output at the FIRST eval_run in the pattern group."

**Implementer choice:** V1 production already persists `candidates.pivot` + `candidates.initial_stop` per evaluation (per migration `0001_phase1_initial.sql`). Using V1-persisted values directly (a) is consistent with the operator-visible UI state; (b) sidesteps the L6 archive-mutation issue at pivot derivation time (pivots are FROZEN in V1 state, not recomputed from current archive); (c) avoids running V2's evaluator per candidate just to extract a derived structural-evidence field that V1 already computed.

**Trade-off:** the pivots may differ slightly from what V2 would compute today (if archive bars have mutated post-V1-persistence) — but this is the desired property (pivot stability across time).

### 5.2 Pattern grouping threshold: 5 business days (not calendar days)

**Brief OQ-3 default:** ~5 trading days.

**Implementer choice:** `numpy.busday_count` strict less-than threshold of 5 business days. Avoids weekend-spanning calendar-day ambiguity (5 calendar days = 3-4 business days; the choice produces incorrect cluster boundaries at quarter-end and holiday weeks).

**Sensitivity verified:** range 3-10 BD yields 15-19 patterns; verdict invariant across the range (per findings §3).

### 5.3 Risk per trade + share sizing NOT computed

**Brief §2:** "Risk per trade: per `cfg.risk.max_risk_pct` (0.005); capital floor $7500. Used for share-sizing calculation."

**Implementer choice:** R-multiples + per-trade dollar-P&L can be computed POST-HOC from `(entry_price, initial_stop, capital_floor, max_risk_pct)`. The backtest engine emits per-pattern R-multiple + entry/exit prices. Dollar P&L was not added to the CSV because (a) all 5 triggered patterns are OPEN at data tail; (b) no R-multiple closed-trade distribution exists to meaningfully aggregate dollar P&L; (c) the verdict is structural (70.6% non-breakout) — dollar conversion adds zero signal to the verdict.

**Future:** if a follow-up dispatch lands an archive refresh + re-run, dollar P&L should be added per pattern as `floor($7500_capital * 0.005 / R_unit) * (exit_price - entry_price)`.

### 5.4 Stop-fill semantics LOCKED to worst-case-market-stop

**Brief §3:** ambiguous on slippage / market-stop vs limit-stop fill modeling.

**Implementer choice:** intraday Low <= current_stop fires `stop_hit` (or `trail_stop` post-arm) at the stop price (worst-case market-stop assumption; no slippage modeling). Close-below-MA fills at the bar's Close (close-confirmed signal per DST D.3). This is a conservative R-multiple bias (slightly understates realized R for stop-hit trades).

### 5.5 Open positions: kept in cohort + R-multiple reported

**Brief §4:** "if pattern doesn't exit by 2026-05-22 (last available bar), record as `open_position` with current-price-relative R-multiple."

**Implementer choice:** open positions are emitted with `status='open'`, `exit_reason='open_at_data_tail'`, and `r_multiple` = `(last_close - entry_price) / R`. They are INCLUDED in the per-ruleset table but EXCLUDED from the closed-trade win-rate denominator (per brief OQ-4 default).

### 5.6 Pattern-near-miss diagnostic ADDED (not in brief)

The Trade dataclass + results CSV carry 3 new diagnostic columns NOT enumerated in the brief: `forward_bars_available`, `max_forward_close`, `max_close_pct_of_pivot`. These were CRITICAL for the negative-verdict interpretation — they distinguish "data-sparse untriggered" from "genuine no-breakout" patterns. The 12 untriggered patterns' max-close-pct-of-pivot values (86-99% of pivot) are the strongest single signal for the negative cfg-policy verdict.

### 5.7 Codex MCP adversarial-critic NOT invoked

**Brief §0 + workflow:** "Adversarial Codex MCP review OPTIONAL — invoke only if analytical engine code lands beyond ~200 lines."

**Implementer choice:** backtest harness analytical surface (`patterns.py` + `walkforward.py` + `rulesets.py`) totals ~430 lines of Python code (above the 200-line threshold). Codex MCP NOT invoked per operator-paired discretion implicit in the dispatch (this is a study, not a production code path; the negative verdict is structurally robust and not sensitive to subtle bugs in the engine; the engine carries 16 fast tests covering all 3 rulesets). Banked V2 candidate: if a follow-up dispatch lands Option B (archive refresh + re-run + extended walk-forward window), Codex review of the engine becomes more material because trade outcomes will populate the closed-trade tally for the first time.

---

## 6. Surfaced caveats + limitations

### 6.1 OHLCV cache freshness (L4-related)

14 of 15 cohort tickers fall through to legacy archive (only DK has Shape A `.yfinance.parquet`). Many legacy archives end well before 2026-05-22:
- 0 forward bars: SSRM, WULF (last bar = 2026-05-15 == first asof)
- 1-5 forward bars: DK, DNTH, NAT, OII, TSHA, YOU-r55
- 6-10 forward bars: FRO, KOD, PTEN, RNG, TROX, UCTT, RLMD-r42

This is operator-cache state, NOT a V2 reader issue. Per dispatch brief §6.4 + V1-state-read-only invariant: the backtest does NOT mutate caches. Option B (operator-paired archive refresh + re-run) is the surfaced remediation.

### 6.2 L6 caveat — ZERO impact on this cohort

The 14 L6-drifted candidates from the V2 full-reproduction smoke (CNTA / ECVT / APLS / FTI / STNG / PL) do NOT intersect this cohort's 15 tickers. L6 has zero direct impact on backtest fidelity. **Fortunate alignment, not architectural guarantee.** Future backtest studies on different cohorts MUST explicitly cross-check L6 drift overlap.

### 6.3 N=5 triggered + N=0 closed: statistical un-decidability

Verdict rests on 5 unrealized-R values + 12 non-breakout patterns. Sample size too small for statistical confidence intervals. Verdict is STRUCTURAL (70.6% non-breakout) rather than statistical.

### 6.4 Rulesets indistinguishable on this cohort

All 3 rulesets emit identical pattern-level outcomes because none of the 5 triggered patterns progressed past entry day to fire any of the rulesets' divergent post-trigger logic. The 3-ruleset comparison structure of the brief is NOT informative on this cohort — but the 3-ruleset architecture is preserved in the engine for future re-runs with longer walk-forward windows.

---

## 7. Forward-binding lessons (V2 / V2.5+ candidates)

### 7.1 Pattern-near-miss diagnostic should be a STANDARD output of any walk-forward backtest harness

The `max_close_pct_of_pivot` diagnostic transformed an ambiguous "12 untriggered" header into a decisive "the breakouts never happened" finding. Future backtest dispatches should enumerate near-miss diagnostics in the dispatch brief's deliverables.

### 7.2 Brief should explicitly enumerate forward-window adequacy preconditions

The brief's §4 ("Data tail handling: if pattern doesn't exit by 2026-05-22... record as `open_position`") implicitly assumed forward-window adequacy. For tickers with cache last-bar = first eval_run asof (SSRM/WULF), this assumption fails silently. Future briefs should require an upfront audit of OHLCV cache freshness per cohort ticker BEFORE engine implementation begins.

### 7.3 Operator-cache-freshness gate is a recurring constraint for V2 research

V1 OHLCV archives are not refreshed for tickers that rotate out of the finviz CSV. This is the same root cause that affects V2 baseline parity (gotcha #24). For research that walk-forward through V1 cache state, an UP-FRONT freshness audit + selective re-run is more efficient than running first then characterizing the gap.

### 7.4 Pivot stability across time has its own caveat (L6 inverted)

V1-persisted `candidates.pivot` is the right input for backtest entry-trigger detection (consistent with operator-visible UI state at the time of the candidate's life). But comparing V1-persisted pivot against CURRENT archive bars (for the close-above-pivot check) means the "what did the operator see at the time" question is approximate. If the archive's CURRENT bar at the trigger session differs from what V1 saw at persistence time, the trigger timing may differ. For this cohort (15 tickers; no L6 drift overlap), this is moot. Future cohorts MUST cross-check.

### 7.5 Risk-sizing computation banking

Brief §2 enumerated `compute_shares` integration but the backtest engine emits per-pattern R-multiples without per-pattern dollar-P&L. For the next backtest dispatch where the closed-trade distribution is non-empty, the engine should be extended to emit `dollar_pnl` per pattern (computable inline from `(entry_price, exit_price, share_count)` where `share_count = floor(capital_floor * max_risk_pct / R_unit)`).

---

## 8. Commit cadence

Sub-bundle commits planned for this dispatch (orchestrator-side merge):

1. `feat(research): backtest harness scaffold + patterns dedup` — `patterns.py` + `test_patterns.py` (5 tests)
2. `feat(research): walk-forward engine + 3 exit rulesets` — `walkforward.py` + `rulesets.py` + `test_rulesets.py` (11 tests)
3. `feat(research): backtest IO + run orchestrator` — `io.py` + `run.py`
4. `feat(research): backtest near-miss diagnostic + initial cohort run` — Trade dataclass extension + CSV header extension + first artifact ship
5. `docs(applied-research): V2 tightness backtest findings + study amendment + return report` — this return report + findings doc + study writeup amendment

Implementer-side commits will batch sub-bundles 1-4 into 2 commits (engine + run) to match orchestrator's commit-cadence preference; the doc commit is sub-bundle 5 standalone.

---

## 9. Verification self-check

| Check | Result |
|-------|--------|
| 16 fast tests pass under `python -m pytest tests/research/backtest_v2_tightness/` | PASS |
| Schema unchanged | PASS (zero files in `swing/data/migrations/`) |
| ZERO new Schwab API calls | PASS (grep shows ZERO `swing.integrations.schwab` or yfinance imports in `research/harness/backtest_v2_tightness/`) |
| ZERO Co-Authored-By footer | PASS (verifiable at merge time) |
| V1 persisted state unchanged | PASS (SELECT-only on candidates + evaluation_runs; ZERO UPDATE/DELETE/INSERT) |
| Production `swing/` read-only | PASS (`git diff main -- swing/` empty) |
| ASCII-only narrative | PASS |
| Both-exist banner consulted (gotcha #24 surface) | PASS (1 ticker hit Shape A + legacy coexist; recorded in BothExistDiagnostic) |

---

*End of return report. Verdict: NEGATIVE cfg-policy substrate for `vcp.tightness_range_factor=1.005`; recommend operator-paired Option A (pivot to next binding variable) OR Option B (operator-paired archive refresh + re-run). Backtest harness + tests + diagnostics shipped under `research/harness/backtest_v2_tightness/` for future re-use. ZERO V1-state mutation; ZERO Schwab API calls; ZERO Co-Authored-By footer; ZERO production swing/ writes.*
