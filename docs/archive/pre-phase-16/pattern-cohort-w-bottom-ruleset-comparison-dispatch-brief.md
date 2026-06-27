# W-Bottom Ruleset Comparison Backtest (D2) — Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the W-bottom ruleset-comparison backtest implementer. No prior conversation context.

**Mission:** Extend D1's NEGATIVE-strict + close-below-50d-exit-mis-calibration findings via two coupled expansions: (a) **cohort expansion** from D1's N=12 patterns (selection-biased "W's that almost-passed a relaxed VCP criterion") to **N=50-200** S&P-500-wide W's (selection-bias-free; same Feb-Apr 2026 regime; same recency<=60d discipline); (b) **ruleset expansion** from D1's 3 conservative-baseline rulesets (Minervini trail-MA / fixed R-multiple / close-below-50d) to **6 rulesets** including 3 NEW literature-canonical variants: **Ruleset D Minervini Stage-2** + **Ruleset E O'Neil cup-with-handle-variant** + **Ruleset F Qullamaggie momentum-burst**. Tests whether ANY literature-canonical ruleset produces closed-and-profitable trades on a statistically-meaningful cohort + whether the D1-confirmed close-below-50d exit-mis-calibration (8/8 closures via single exit mode at -0.469R mean) can be CORRECTED by literature-canonical alternatives.

**Workflow:** `copowers:executing-plans` skill (wraps `superpowers:test-driven-development` + Codex MCP adversarial review). Codex MCP invocation per pre-dispatch operator-paired decision (see §11 below; recommendation: invoke given substantial scope mirrors D1's 38th cumulative C.C lesson #6 validation precedent).

**Branch:** `applied-research-w-bottom-ruleset-comparison` — branches from main HEAD `6aa3fa7` (or later; reflects Turn F post-archive-refresh D1 Amendment 2).

**Worktree:** `git worktree add .worktrees/applied-research-w-bottom-ruleset-comparison applied-research-w-bottom-ruleset-comparison`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~6-10 hours operator-paced + ~1-2h Codex chain. Substantial new analytical surface BUT extensively reuses D1's harness modules.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/pattern-cohort-double-bottom-w-backtest-findings-2026-05-25.md`** — D1 findings doc. Especially Section 1 (verdict) + Section 4 (mechanism analysis) + **Section 11 Amendment 2** (post-archive-refresh re-run; close-below-50d exit-rule mis-calibration CONFIRMED via 8/8 closures via single exit mode). The Amendment substantively motivates THIS dispatch's ruleset choices.

3. **`docs/pattern-cohort-double-bottom-w-backtest-return-report.md`** — D1 return report. Especially Section 5 V2 banked candidates (#3 close-below-50d arming gate; THIS dispatch implements it across 3 new rulesets) + Section 7 Codex chain documentation (4 rounds; 0C + 14M + 11m converged).

4. **`docs/pattern-cohort-double-bottom-w-backtest-dispatch-brief.md`** — D1 dispatch brief. Reuse §1.3 pattern dedup discipline; §2 entry rule (close > center_peak_price); §3 stop placement (trough_2 × 0.99); §4 output shape (27-column CSV per Codex R3 M#2).

5. **`research/harness/double_bottom_w_backtest/`** — D1 harness modules (5 modules: cohort.py + walkforward.py + rulesets.py + io.py + run.py). **THIS dispatch reuses cohort.py + walkforward.py + io.py + run.py mostly verbatim; rulesets.py extends from 3 to 6 rulesets; cohort fixture generation is NEW work.**

6. **`research/method-records/pattern-cohort-detection.md`** v0.1.1 — pattern_cohort_evaluator method record. Especially L5 (exemplar OHLCV provisioning discipline; gotchas #28 + #29) — the expanded-cohort smoke MUST run with deep-exemplar archives already in place (these were refreshed Turn F bug #3 fix; should still be current).

7. **`reference/methodology/`** — Minervini canonical text (in project; primary literature source per operator decision 2026-05-25 PM).

8. **`reference/methodology/`** — O'Neil "How to Make Money in Stocks" cup-with-handle chapter — IF present in project tree. If absent, source canonical O'Neil cup-with-handle rules from any reliable secondary citation (e.g., Bulkowski "Encyclopedia of Chart Patterns" double-bottom chapter is an acceptable proxy per spec section 5 below).

9. **`mcp__qullamaggie__*` MCP tools** — the qullamaggie MCP server (per CLAUDE.md operator memory `reference_qullamaggie_mcp`) at `localhost:9871` provides Qullamaggie trading commentary KB. Use `mcp__qullamaggie__query_trading_rules` + `mcp__qullamaggie__get_setup_criteria` + `mcp__qullamaggie__search_transcripts` to source canonical Qullamaggie momentum-burst entry / exit / position-sizing rules for Ruleset F specification refinement.

10. **CLAUDE.md** gotchas #1-#32 — cumulative discipline. Especially:
    - **#26** — archive bar-content TEMPORAL mutation (forward bars from CURRENT archive; document caveat)
    - **#28 + #29** — OHLCV cache discipline (cohort smoke needs deep exemplar archives; already in place post-Turn-F bug-#3 fix)
    - **#30** — recency/filter/dedup semantic-ordering audit (this brief inherits D1's max_observed_asof + effective_asof discipline)
    - **#31** — narrative artifact path/fact lag (post-fix smoke updates require narrative-doc sweep)
    - **#32** — ASCII discipline scope clarity (declare scope explicitly across all files)

11. **`exports/research/double-bottom-w-backtest-20260525T131423Z/`** — post-refresh D1 smoke artifact (the substantive substrate motivating this dispatch's rulesets).

---

## §1 Cohort expansion scope

### §1.1 Universe + asof-date schedule

**Universe:** S&P 500 tickers per `cfg.paths.rs_universe_path` (typically `data/finviz-inbox/sp500-universe.csv` OR the operator's recent A+/watchlist; the cfg field is single-source-of-truth).

**Asof-date schedule:** **4 dates from 2026-02 → 2026-04** (one per ~3-week interval; covers the same regime as D1's Feb-Apr asof cluster):
- 2026-02-06 (first Friday of Feb)
- 2026-02-27 (last Friday of Feb)
- 2026-03-27 (last Friday of Mar)
- 2026-04-17 (third Friday of Apr; before the asof-too-recent cutoff per D1's YOU-2026-04-29 untriggered finding)

**Total cohort input:** ~500 tickers × 4 asof dates = ~2000 (ticker, asof_date) entries.

### §1.2 Cohort generation procedure

1. **Generate cohort CSV** at `exports/research/cohorts/w_bottom_ruleset_comparison_sp500_feb_apr_2026.csv` with columns `ticker,asof_date` (matches pattern_cohort_evaluator's input schema). Cohort label optional but RECOMMENDED for traceability.

2. **Run pattern_cohort_evaluator** via:
   ```powershell
   python -m swing.cli diagnose pattern-cohort-detect `
     --cohort-csv exports/research/cohorts/w_bottom_ruleset_comparison_sp500_feb_apr_2026.csv `
     --db "$env:USERPROFILE/swing-data/swing.db" `
     --output-dir exports/research/ `
     --pattern-class-filter double_bottom_w
   ```
   Expected runtime: ~30-60 min for ~2000 entries (vs ~8 min for D1's 67 entries).

3. **Extract D1-style cohort fixture** from the new pattern_cohort_evaluator results.csv via existing D1 cohort module's filter + dedup pipeline:
   - Filter `pattern_class == 'double_bottom_w' AND composite_score >= 0.7`
   - Per-(ticker, trough_1_date) primary-by-highest-composite dedup
   - 5-BD adjacency merge per D1 §1.3
   - Recency filter: trough_2 within 60 cal days of `max_observed_asof_date` per D1 Codex R1 M#3 + R2 M#1 discipline
   - **Expected post-filter count: N=50-200 unique W patterns.** If N<30, expand asof-date schedule to 6 dates. If N>300, tighten recency to 45d OR composite threshold to 0.75 (document deviation in findings).

4. **Persist new cohort fixture** at `tests/fixtures/research/w_bottom_ruleset_comparison/cohort.json` (mirrors D1 fixture shape exactly).

### §1.3 Pre-flight checks before backtest

- Verify all exemplar tickers still have deep archives (per Turn F bug #3 fix; gotcha #29 family); if depth-insufficient surfaces, run `tmp/bug-3-exemplar-ohlcv-deep-fetch.py` style script first.
- Verify D1 cohort tickers' archives are still current (post-Turn-F-refresh state at `6aa3fa7`); the 10 D1 tickers should be at 2026-05-22 last bar.
- **NEW**: verify all NEW cohort tickers (likely ~30-50 unique tickers post-filter) have legacy archives in `~/swing-data/prices-cache/`. For any missing OR stale beyond 7 days, run yfinance `period="max"` refresh (mirror Turn F's `tmp/d1-cohort-archive-refresh.py` pattern). Document any tickers requiring refresh in findings.

---

## §2 Entry rule (UNCHANGED from D1)

Per D1 dispatch brief §2 + walk-forward module — REUSE verbatim:

- **Trigger**: first daily close > `center_peak_price` AFTER `effective_asof_date + 1 BD` (where `effective_asof_date = max(anchor_asof, max_observed_asof)` per D1 Codex R2 M#1)
- **Entry**: next-session OPEN following the trigger close
- **Initial stop**: `trough_2_price * 0.99` (canonical W right-shoulder)
- **Trigger search window**: `effective_asof + 1 BD` lower bound, `effective_asof + 60 BD` upper bound

ALL 6 rulesets use the SAME entry mechanics. Only post-entry trade management differs.

---

## §3 Six rulesets — 3 baseline + 3 NEW literature-canonical

### §3.1 Ruleset A — Minervini trail-MA (UNCHANGED from D1)

Per D1 dispatch brief §3.1. Baseline; included for cross-comparison. Initial stop trough_2 × 0.99; trail via 10-day SMA after position is in profit; hard exit on close <= 50d SMA. NO arming gate (D1 spec).

### §3.2 Ruleset B — Fixed R-multiple (UNCHANGED from D1)

Per D1 dispatch brief §3.2. Mechanical; baseline. Initial stop trough_2 × 0.99; target = entry + 3R; no trail; exit at target OR initial stop.

### §3.3 Ruleset C — Close-below-50d (UNCHANGED from D1)

Per D1 dispatch brief §3.3. Baseline; included to verify D1's confirmed mis-calibration finding scales to larger N. Initial stop trough_2 × 0.99; hard exit on close <= 50d SMA. NO arming gate (D1 spec; the mis-calibration baseline).

### §3.4 Ruleset D — Minervini Stage-2 stop-progression (NEW)

Per `reference/methodology/` Minervini canonical text + Stage Analysis framework. Operator decision 2026-05-25 PM: Minervini is canonical.

**Specification:**
- **Initial stop**: `trough_2_price * 0.99` (mirrors D1 baseline)
- **Stop-to-breakeven arm**: when unrealized R >= +2.0R (close-based), raise stop to entry_price (no slippage credit)
- **Trail rule (after breakeven arm fires)**: trail stop to `max(prior_stop, 10d_SMA * 0.99)` daily, computed on each session's close
- **Hard exit gate (NEW; per D1 Codex R1 V2 candidate #3)**: close <= 50d_SMA EXIT fires ONLY IF `50d_SMA > entry_price * 1.05` (i.e., the 50d is at least 5% above entry; ensures W has demonstrably moved beyond the 50d influence zone before close_below_50d can fire)
- **Time-based exit (per Minervini Stage 2 → Stage 3 detection)**: optional V2 candidate; NOT in V1 scope
- **Trade window**: until breakeven-trail stop OR 50d-gated-hard-exit OR archive end

**Rationale**: Minervini's Stage-2-uptrend framework treats the post-base-breakout phase as the highest-probability hold period. Stop-to-breakeven at +2R = "free trade" risk management. 10d SMA trail = tight enough to lock in gains without premature exit on normal volatility. 50d gate = primary defense against trend break, but ONLY ARMED when price has clearly moved into Stage 2.

### §3.5 Ruleset E — O'Neil cup-with-handle-variant + Bulkowski measured-move target (NEW)

Per O'Neil "How to Make Money in Stocks" cup-with-handle chapter + Bulkowski "Encyclopedia of Chart Patterns" double-bottom measured-move rule. Operator decision: O'Neil for cases outside Minervini's norm; double-bottom is specifically outside Minervini's primary VCP frame.

**Specification:**
- **Initial stop**: `entry_price * 0.92` (8% below entry; O'Neil's canonical max stop loss; LOOSER than trough_2 × 0.99 if trough_2 is far below entry — use whichever is HIGHER as the actual stop for risk-control: `max(trough_2 * 0.99, entry_price * 0.92)`)
- **Measured-move target (Bulkowski canonical for double-bottom)**: `target = entry_price + (center_peak_price - min(trough_1_price, trough_2_price))` — the height of the W projected from the breakout level
- **Target exit**: fires on first daily close >= target
- **Stop exit**: fires on first daily close <= initial stop
- **No trail; no time-based exit** (O'Neil cup-with-handle base case)
- **Trade window**: until target OR stop OR archive end

**Rationale**: O'Neil's cup-with-handle framework (which W-bottoms are a structural variant of) uses 8% max loss + measured-move target as the canonical risk-reward frame. Bulkowski's measured-move formula is the explicit double-bottom target rule. Tests whether a CANONICAL TARGET (not trail-based) produces winners that the D1 50d-floor exit prevented.

### §3.6 Ruleset F — Qullamaggie momentum-burst extension (NEW)

Per qullamaggie MCP server canonical commentary (use `mcp__qullamaggie__get_setup_criteria` + `mcp__qullamaggie__query_trading_rules` to source exact rule semantics).

**Specification (sketch; refine via MCP query during execution):**
- **Initial stop**: same as Ruleset D — `trough_2_price * 0.99`
- **Momentum confirmation gate**: position MUST advance >= +1.0 ATR within 5 sessions of entry; ELSE close-and-exit at next session open (no continuation = no commitment)
- **First profit-take**: scale out 1/3 at +2R (close-based); raise stop on remaining position to entry price (breakeven)
- **Trail rule (remaining 2/3)**: trail stop daily to `max(prior_stop, 20d_SMA)` AFTER first profit-take fires
- **Hard exit gate (NEW; mirror D1 V2 candidate #3 + D's gate)**: close <= 50d_SMA EXIT fires ONLY IF `50d_SMA > entry_price * 1.05`
- **Trade window**: until 5-session momentum-fail OR breakeven-stop on remaining OR 50d-gated-hard-exit OR archive end

**Rationale**: Qullamaggie's framework emphasizes momentum burst confirmation + active position management (scale-out + breakeven) vs Minervini's hold-the-full-position approach. Tests whether SCALE-OUT mechanics produce more closed-and-profitable trades on the W cohort.

---

## §4 Output / analytical surface

### §4.1 Per-pattern per-ruleset CSV

`exports/research/w-bottom-ruleset-comparison-<ISO>/results.csv` — **6-ruleset variant** of D1's 27-column schema. Row count: unique_pattern_count × 6 rulesets. Expected: 50-200 × 6 = 300-1200 rows.

Schema: same 27 columns as D1 post-Codex-R3-M#2 (anchor_asof_date + effective_asof_date + max_observed_asof_date + entry_session + entry_price + initial_stop_price + exit_session + exit_price + exit_reason + trade_pnl_R + trade_pnl_dollars + peak_unrealized_R + drawdown_to_exit_R + sessions_held + composite_score + geometric_score + template_match_score + ticker + ruleset + ... etc.).

NEW: Ruleset enum values extended with `D_minervini_stage2_progression`, `E_oneil_cup_with_handle_measured_move`, `F_qullamaggie_momentum_burst`.

### §4.2 Per-ruleset analytical markdown summary

`exports/research/w-bottom-ruleset-comparison-<ISO>/summary.md` — sections:
- Headline: per-ruleset win/loss counts + R distribution (mean / median / std) + Sharpe-like ratio
- **Cross-ruleset comparison table** (NEW): 6 rulesets × {win_rate, mean_R, expectancy, max_drawdown, hold_time} — direct comparison; rank by expectancy
- Per-ticker breakdown for each ruleset
- Per-composite-score-bucket analysis (composite>=0.9 vs 0.7-0.9 — does higher composite predict higher win rate? does it predict differently across rulesets?)
- Per-exit-reason distribution (Ruleset D + F gate-on-50d should produce DIFFERENT exit-reason distribution than C unmodified)
- Comparison vs D1 N=12 cohort (post-archive-refresh results from `131423Z`)
- Comparison vs V2 OHLCV backtest at `e0a9edd`

### §4.3 Manifest JSON

`exports/research/w-bottom-ruleset-comparison-<ISO>/manifest.json` — cohort SHA-256 + 6-ruleset enumeration + per-ruleset patterns_count + runtime + L2 LOCK sentinel + V1 source-ladder consistency check + source provenance fields per D1 Codex R1 M#5 (link to upstream pattern_cohort_evaluator manifest hash).

---

## §5 Discriminating tests (~25-35 fast tests)

At `tests/research/w_bottom_ruleset_comparison/`:

### §5.1 Cohort fixture generation (~5 tests)

- Generate cohort CSV with synthetic S&P 500 stub list + 4 asof dates; verify CSV shape + column ordering.
- Run cohort fixture extractor against synthetic results.csv; verify recency filter + dedup pipeline yields expected count.
- Verify max_observed_asof_date propagates correctly across multiple-asof observations.

### §5.2 Per-new-ruleset tests (~6 tests per ruleset × 3 rulesets = ~18 tests)

For each of Rulesets D, E, F:
- Synthetic position with known entry / stop / target / trail; assert exit fires at correct session + price.
- Boundary cases: stop fires same session as target (e.g., gap-down close below stop after gap-up); assert stop wins per close-based discipline.
- Trail rule semantics: synthetic +3R move; assert trail raises stop; assert subsequent close-below-trail fires exit.
- D-specific: 50d-arming-gate semantics (close <= 50d fires only when 50d > entry × 1.05); synthetic with 50d > entry × 1.05 AND 50d <= entry × 1.05 cases.
- E-specific: measured-move target = entry + (center_peak - min(trough_1, trough_2)); synthetic with known W structure verifies target value.
- F-specific: 5-session momentum gate; scale-out 1/3 at +2R + breakeven on remaining; trail on 20d SMA after scale-out.

### §5.3 Cross-ruleset comparison (~3 tests)

- Same synthetic pattern across 6 rulesets; verify rulesets D/E/F differ from A/B/C as expected.
- Cross-ruleset aggregate statistics: synthetic cohort of 10 patterns; assert summary computes correct mean R per ruleset.

### §5.4 L2 LOCK BINDING (~2 tests; same pattern as D1)

- Import-graph sentinel post-import via sys.modules audit.
- Source-grep sentinel for yfinance/schwabdev/swing.integrations.schwab in NEW module source files.

### §5.5 Cohort scope assertion (~2 tests)

- Assert pattern_cohort_evaluator runs against ~500 × 4 = ~2000 entries (NOT D1's 67) when given expanded cohort CSV.
- Assert post-filter cohort size is in [30, 300] range; outside range fires a warning (per §1.2 step 3 guidance).

---

## §6 Acceptance criteria

### §6.1 Functional

- [ ] Cohort CSV generated at correct path with ~2000 entries.
- [ ] pattern_cohort_evaluator smoke produces NEW artifact at `exports/research/pattern-cohort-detection-<ISO>/`.
- [ ] D1-style cohort fixture generated at `tests/fixtures/research/w_bottom_ruleset_comparison/cohort.json`.
- [ ] All 6 rulesets emit correct per-pattern outcomes per their canonical specs.
- [ ] Manifest `l2_lock_preserved: true`.

### §6.2 Test scope

- [ ] 25-35 NEW fast tests at `tests/research/w_bottom_ruleset_comparison/`.
- [ ] All existing tests still green (baseline ~6054 fast tests at Turn F D1 merge; this dispatch adds 25-35 → ~6079-6089).
- [ ] `python -m pytest tests/research/ -m "not slow" -q` exits 0.

### §6.3 Discipline preservation

- [ ] ZERO Co-Authored-By footer drift (preserve ~534+ cumulative streak through `6aa3fa7`).
- [ ] ZERO production swing/ writes beyond OQ-13-mirror CLI carve-out (mirror D1's 80-line precedent; budget ~80-100 lines for the new subcommand `swing diagnose w-bottom-ruleset-comparison`).
- [ ] Schema v21 unchanged.
- [ ] ZERO new Schwab API calls (L2 LOCK).
- [ ] ASCII discipline COMPLETE across ALL files per gotcha #32 (declare scope explicitly: narrative-docs + source + tests + smoke artifacts + manifest JSON + CLI help text).

### §6.4 Analytical deliverables

- [ ] `exports/research/w-bottom-ruleset-comparison-<ISO>/` artifact directory with results.csv + summary.md + manifest.json.
- [ ] `docs/pattern-cohort-w-bottom-ruleset-comparison-findings-<ISO>.md` — analytical narrative; mirror D1 findings doc shape.
- [ ] Cross-tabulation vs D1 N=12 cohort (post-refresh 131423Z) MANDATED in findings doc.

### §6.5 Verdict classification (D2 version)

Adapted from D1 §7.5 to account for the 6-ruleset comparison structure:

- **POSITIVE**: at least 1 of {D, E, F} produces (a) mean-R closed > 0 across all closed trades AND (b) win-rate >= 35% AND (c) at least 5 closed-and-profitable trades. Implication: literature-canonical ruleset unlocks W-bottom expectancy; R1 + R2 hypotheses CONFIRMED.
- **PARTIAL**: at least 1 of {D, E, F} produces (a) mean-R closed > 0 across all closed trades AND (b) win-rate >= 25% AND (c) at least 3 closed-and-profitable trades, but does NOT meet POSITIVE thresholds. Implication: directional support; recommend tighter cohort (e.g., composite>=0.9 only) OR multi-cohort validation (R2 path on next binding variable) before deployment decision.
- **NEGATIVE**: ALL of {D, E, F} have either (a) mean-R closed <= 0 OR (b) win-rate < 25% OR (c) fewer than 3 closed-and-profitable trades. Implication: literature-canonical W-bottom rulesets do not unlock expectancy on this cohort; the R1 hypothesis (chart-shape-appropriate triggers) is necessary but not sufficient EVEN with literature-canonical exits; R3 path (treat sensitivity analysis as upstream diagnostics) reinforced.
- **AMBIGUOUS**: ranking across {D, E, F} is statistically indistinguishable (within 1 std of expectancy). Implication: cohort too small OR rulesets too similar to discriminate.

Acceptance criteria §6.4 findings doc MUST classify verdict + cite which ruleset (if any) reached POSITIVE / PARTIAL bars.

---

## §7 Watch items + cumulative discipline (BINDING)

### §7.1 Cumulative discipline (32 gotchas BINDING for 40th cumulative validation onwards)

If Codex MCP review invoked, ALL 32 gotchas BINDING. **ESPECIALLY relevant to this dispatch**:

- **#26** — archive bar-content TEMPORAL mutation: forward bars from CURRENT archive may differ from contemporaneous V1 state. Document caveat in findings.
- **#28 + #29** — exemplar OHLCV cache discipline + depth-insufficiency: cohort smoke + backtest require deep exemplar archives; verify pre-flight per §1.3.
- **#30** — recency/filter/dedup semantic-ordering audit: inherit D1's max_observed_asof + effective_asof discipline verbatim; do NOT regress.
- **#31** — narrative artifact path/fact lag: if multiple Codex round fix-bundles emit new smoke artifacts, sweep narrative docs path + facts post-bundle.
- **#32** — ASCII discipline scope clarity: declare scope EXPLICITLY across all N files at writing-plans / pre-Codex review time.
- **#21** — cumulative regression cascade audit in fix loops: 5 Codex R1-R3 rounds at D1 surfaced 3-instance cascades (M#3 → R2.M#1 → R3.M#2); be alert for similar restructuring-induced regressions.
- **#22 + #23** — per-counter-accumulation + dataclass attribution metadata: 6-ruleset CSV emit has more attribution surface than D1's 3-ruleset; ensure per-(pattern, ruleset) ID propagation is correct everywhere.

### §7.2 Per-dispatch watch items

- (a) **Cohort generation runtime budget**: ~2000-entry pattern_cohort_evaluator runs ~30-60 min. If >2h, abort + reduce asof-date count OR universe size; document.
- (b) **Ruleset specification authority**: Minervini spec sources from `reference/methodology/` (project text; primary); O'Neil sources from O'Neil chapter IF present in project tree OR Bulkowski as proxy citation; Qullamaggie sources from MCP server queries during execution. Document the source citation for each ruleset's rules in the findings doc + return report.
- (c) **5-session momentum gate (Ruleset F)**: requires intraday peek at +1.0 ATR within 5 sessions. ATR = 14-day average true range. If position never advances >= +1.0 ATR within 5 sessions of entry, exit at session 6 open. Discriminating test must verify this gate fires correctly + correctly DOES NOT fire when momentum threshold met.
- (d) **Measured-move target (Ruleset E)**: `target = entry + (center_peak - min(trough_1, trough_2))`. Verify the per-pattern target value via discriminating test.
- (e) **Cross-ruleset CSV column extension**: 6 distinct ruleset enum values; verify ruleset column accepts all 6; output column count = 27 (UNCHANGED from D1 schema; row count grows to 300-1200).
- (f) **N=50-200 expected post-filter cohort size**: if N<30, brief authors should be alerted (the assumption may be wrong; widen asof-date schedule). If N>300, tighten composite threshold OR recency. Document in findings.

### §7.3 Cross-comparison with D1 + V2 backtest

Findings doc §[X] MUST cross-tabulate:
- **D2 vs D1** (post-refresh 131423Z): per-ticker overlap (10 D1 tickers should ALL appear if S&P 500 universe covers them; possibly some D1 tickers may now have DIFFERENT W primary verdicts due to different asof dates); per-pattern overlap; per-outcome delta.
- **D2 vs V2 OHLCV backtest** at `e0a9edd`: trigger rate; closed-and-profitable count; mean-R.

### §7.4 Codex MCP decision

OPERATOR-PAIRED PRE-DISPATCH decision. Recommendation (per D1 precedent):
- 6-ruleset structure + new analytical surface + new cohort generation pipeline = substantial new scope (mirrors D1; >300 lines new code expected)
- Pre-Codex 12-expansion + 32-gotcha BINDING discipline
- 39th cumulative C.C lesson #6 validation slot RESERVED post-D1 (38th was D1's 4-round chain)

Operator may choose to invoke Codex MCP for the 39th slot OR defer.

---

## §8 Commit cadence + return report

### §8.1 Commit cadence

TDD slice discipline (~12-18 commits):
1. Cohort CSV generation test (RED) + impl (GREEN)
2. pattern_cohort_evaluator orchestration + smoke artifact verification
3. D1-style cohort fixture extractor test + impl
4. Per-new-ruleset implementation tests (one commit per ruleset; 3 commits)
5. Cross-ruleset comparison aggregator test + impl
6. End-to-end backtest runner test + impl
7. Output emitter extension (CSV / summary / manifest)
8. CLI wiring (NEW `diagnose w-bottom-ruleset-comparison` subcommand; mirror D1)
9. Smoke artifact generation + commit
10. Findings doc + return report
11. Codex MCP review chain fix bundles (if invoked)

### §8.2 Return report

Author at `docs/pattern-cohort-w-bottom-ruleset-comparison-return-report.md`. Sections mirror D1's return-report shape (§0 TL;DR + §1 commits + §2 tests + §3 smoke + §4 discipline + §5 V2 candidates + §6 deviations + §7 Codex chain + §8 cross-tabulation + §9 verdict + recommendations).

---

## §9 Branch + worktree setup

```powershell
# From the repo root:
git checkout main
git pull origin main
git worktree add .worktrees/applied-research-w-bottom-ruleset-comparison -b applied-research-w-bottom-ruleset-comparison
cd .worktrees/applied-research-w-bottom-ruleset-comparison
# Verify branch + working tree are clean
git status
git log --oneline -5
# Work begins from here. Use `python -m swing.cli` (NOT bare `swing`).
```

When done:
- Push branch: `git push -u origin applied-research-w-bottom-ruleset-comparison`
- Author findings doc + return report
- Notify orchestrator for merge

---

## §10 Do NOT

- Modify production `swing/` beyond an OQ-13-mirror CLI carve-out (~80-100 lines)
- Modify V1 persisted state
- Trigger Schwab API calls (L2 LOCK BINDING + REINFORCED)
- Modify any schema (v21 LOCKED)
- Pre-fetch additional OHLCV data via yfinance for the cohort universe UNLESS verified missing/stale (yfinance has rate limits; mass-refresh of S&P 500 is multi-hour + risky)
- Add Co-Authored-By footer to ANY commit
- Iteratively tune ruleset parameters against the same cohort to find a "winning" configuration — that's overfit; rulesets D + E + F are SPECIFIED A PRIORI per literature canonical; if results are NEGATIVE for all 3, the verdict is NEGATIVE (do NOT post-hoc adjust to find a winner)
- Use D1's narrow N=12 cohort directly — that's the cohort selection bias this dispatch is correcting
- Skip the Qullamaggie MCP queries during execution — Ruleset F spec depends on canonical source
- Skip the cross-comparison vs D1 + V2 in the findings doc

---

*End of dispatch brief. Substantial cohort + ruleset expansion; tests whether literature-canonical W-bottom exit rules (Minervini Stage-2 / O'Neil cup-with-handle-variant / Qullamaggie momentum-burst) unlock expectancy on a statistically-meaningful S&P-500-wide W cohort. Reuses D1 harness extensively; new code ~300-500 lines + ~25-35 tests. Verdict classification adapted to 6-ruleset structure; A priori ruleset specs; no post-hoc tuning permitted.*
