# Double-Bottom-W Walk-Forward Backtest Study — Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the double-bottom-W walk-forward backtest study implementer. No prior conversation context.

**Mission:** Take the subset of the +67 watch->aplus cohort (at `vcp.tightness_range_factor=1.005`) where the Phase 13 `double_bottom_w` detector emits `composite_score >= 0.7` post-template-Pass-2 + walk forward from each pattern's `data_asof_date` using a **W-right-shoulder-neckline-break entry rule + 3 exit rulesets** (Minervini trail-MA, fixed R-multiple, close-below-50d-SMA). This tests the **Turn F B study writeup's R1 reframing hypothesis**: the prior V2 OHLCV backtest at `e0a9edd` returned NEGATIVE for `vcp.tightness_range_factor=1.005` (5/17 triggered = 29% rate; 0 closed; -0.18R mean unrealized) because the `close > consolidation_pivot` entry rule was VCP-appropriate AND mechanically mismatched against the cohort's actual chart shape (double-bottom-w-dominated; per study Conclusion + Interpretation S4). D1 swaps the entry rule to W-right-shoulder break + tests whether the dominant detector signal has positive expectancy under mean-reversion-appropriate rules.

**Workflow:** `superpowers:test-driven-development` skill (study-scoped; reproducible-fixtures pattern). Adversarial Codex MCP review OPTIONAL — invoke if new analytical modules land beyond ~200 lines OR if operator-paired pre-dispatch decision lands invocation.

**Branch:** `applied-research-pattern-cohort-double-bottom-w-backtest` — branches from main HEAD `bbe0a0b` (or later; reflects Turn F bug #3 fix + B amendment shipped).

**Worktree:** `git worktree add .worktrees/applied-research-pattern-cohort-double-bottom-w-backtest applied-research-pattern-cohort-double-bottom-w-backtest`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~4-8 hours operator-paced. Mirrors V2 OHLCV backtest scope (`e0a9edd`); new analytical surface (`research/harness/double_bottom_w_backtest/`); 16-20 fast tests; substantive analytical output.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`research/studies/2026-05-24-pattern-cohort-detection.md`** Results + Interpretation (§S4) + Conclusion (§R1). The Turn F B amendment shipped at `bbe0a0b` ratifies the double-bottom-w-dominated cohort finding. R1 (THIS dispatch) is the Conclusion's first reframing option.

3. **`exports/research/pattern-cohort-detection-20260525T201617Z/summary.md`** — the ratification smoke. `double_bottom_w` section drill-down (lines 82-148+) enumerates the cohort entries at composite>=0.7 sorted by composite_score. **Implementer task §1.1 is to extract verbatim filtered to composite_score >= 0.7.**

4. **`exports/research/pattern-cohort-detection-20260525T201617Z/manifest.json`** — cohort SHA-256 + `cache_dir` field for source-of-truth on the OHLCV archive path (`prices-cache` hyphen per L8 lesson).

5. **`swing/patterns/double_bottom_w.py`** — `DoubleBottomWEvidence` dataclass (lines 117-194); especially `center_peak_price` (neckline; THE entry-trigger reference) + `trough_2_price` (right shoulder low; THE stop-placement reference). `pivot_price` (line 154) is the last close in the candidate window per `_evaluate_criteria_pass` (line 594) and is NOT actionable as a trigger; trigger is `close > center_peak_price` instead.

6. **`docs/v2-tightness-range-factor-backtest-dispatch-brief.md`** + **`docs/v2-tightness-range-factor-backtest-findings-2026-05-24.md`** — prior V2 backtest dispatch + findings. **THIS dispatch parallels the structure; reuse the same 3-ruleset exit semantics + the same pattern-deduplication discipline + the same R-multiple emission shape.**

7. **`reference/methodology/`** — Minervini + Disciplined Swing Trader reference texts for exit-rule semantics. Especially Minervini's trail-MA / Stage-2-uptrend exit rules.

8. **`swing/data/ohlcv_archive.py`** (`read_or_fetch_archive`) — V1's read path. Backtest walk-forward must use the same path to maintain L2 LOCK consistency (legacy parquet read; ZERO Schwab API calls; ZERO yfinance fetch beyond what V1 production would do).

9. **`research/method-records/pattern-cohort-detection.md`** v0.1.1 (Turn F amendment at `bbe0a0b`) — especially L5 (exemplar OHLCV provisioning) + L6 (cache_dir path) lessons. Backtest inherits L1-L6 caveats.

10. **CLAUDE.md** gotchas #1-#29 — cumulative discipline. Especially:
   - **#28 + #29 family** — OHLCV cache discipline; the backtest READS the cache (forward walk from each pattern's data_asof_date through subsequent bars); the same path/depth disciplines apply.
   - **#26** — archive bar-content TEMPORAL mutation; forward bars are walked from CURRENT archive at backtest time; may differ from contemporaneous V1 state. Document as caveat (consistent with V2 OHLCV backtest's L6 caveat).
   - **#25** — sentinel-bucket parity-comparison discipline; not directly applicable but informs the principle that backtest counters MUST distinguish (a) pattern triggered + (b) entry executed + (c) trade closed + (d) outcome class.

---

## §1 Backtest population — candidate list

### §1.1 Source filter

Source: `exports/research/pattern-cohort-detection-20260525T201617Z/results.csv` (untracked due to ~275 MB GitHub limit per `.gitignore` exception; deterministically regeneratable via `python -m swing.cli diagnose pattern-cohort-detect --cohort-csv exports/research/cohorts/tightness_1.005_flips_67.csv --db "$env:USERPROFILE/swing-data/swing.db" --output-dir exports/research/` against an archive in the same shape as cohort SHA-256 `5333afe3...`).

Filter: `pattern_class == 'double_bottom_w' AND composite_score >= 0.7`. Expected: **725 verdicts** per the post-bug-#3-fix smoke artifact's headline summary table.

### §1.2 Pre-extracted summary (orchestrator-side; for sanity-check at fixture construction)

From `exports/research/pattern-cohort-detection-20260525T201617Z/summary.md` double_bottom_w drill-down (capped at first 50 rows by composite_score; full 725-row enumeration in results.csv).

Top tickers at composite>=0.9 (86 verdicts total across these tickers):
- YOU (multiple windows at composite 0.9333)
- DK (windows 76 + 79 at composite 0.9333)
- WULF (windows 41 + 205 at composite 0.9333)
- TSHA (window 142 at composite 0.9333)
- NAT (windows 50 + 52 at composite 0.9333)
- RLMD (windows 15 + 79 at composite 0.9333)
- UCTT (window 54 at composite 0.9333)
- PTEN (window 113 at composite 0.9333)
- KOD (window 116 at composite 0.9333)
- RNG (window 124 at composite 0.9333)
- TROX (windows 23 + 98 at composite 0.9333)

Implementer task §1.2: from results.csv, group rows by `(ticker, asof_date)` to identify unique cohort entries; then group those by ticker to identify unique "patterns" per ticker; the 725 verdicts at composite>=0.7 collapse to roughly **15-30 unique W-bottom patterns** (one per distinct W-shape per ticker).

### §1.3 Pattern-level deduplication

**Per-(ticker, anchor_window) deduplication.** Each cohort entry (`cohort_entry_id, ticker, asof_date`) may emit multiple `window_index` rows for the SAME W-bottom pattern (the harness emits one verdict per candidate window per pattern_class). Furthermore, consecutive `asof_date` values per ticker likely represent the SAME W-bottom persisting across sessions (mirrors V2 backtest's eval_run cluster discipline at §1.2).

Deduplication rule (per V2 backtest precedent):
1. Group verdicts by `(ticker, anchor_window_first_bar_date)` — extracting anchor date from `DoubleBottomWEvidence.trough_1_date` (the W's first trough; the structural anchor).
2. For each `(ticker, trough_1_date)` group: select the verdict with HIGHEST `composite_score` as the pattern's "primary" verdict; record the others as "auxiliary" (same pattern; different windows within the same W).
3. Patterns whose `trough_1_date` differs by <5 trading days within a ticker = same W; merge.

Expected: ~10-20 unique W-bottom patterns from the 725-verdict cohort. Implementer task §1.3 reports the unique pattern count + per-pattern entry/exit/outcome.

### §1.4 Cohort fixture file

Implementer authors: `tests/fixtures/research/double_bottom_w_backtest/cohort.json` — list of unique pattern records, each with:
- `ticker: str`
- `anchor_asof_date: str` (ISO; the asof_date of the primary verdict)
- `trough_1_date: str` (ISO; from primary verdict's evidence)
- `trough_1_price: float`
- `center_peak_date: str` (ISO)
- `center_peak_price: float` (THE trigger reference)
- `trough_2_date: str` (ISO)
- `trough_2_price: float` (THE stop reference)
- `pivot_price: float` (NOT actionable as trigger; recorded for context)
- `composite_score: float`
- `geometric_score: float`
- `template_match_score: float | None` (None if Pass 2 didn't fire for this window — DTW band infeasibility per cumulative T2.SB5 gotcha)
- `window_count: int` (auxiliary windows merged into this pattern)

---

## §2 Entry rule

**Trigger**: First daily close > `center_peak_price` (W-bottom neckline breakout) AFTER `max(trough_1_date, trough_2_date, anchor_asof_date)`.

**Rationale**: Canonical W-bottom technical analysis pattern. trough_1 -> center_peak -> trough_2 forms the W; the recovery completes when price breaks ABOVE the neckline (center_peak). Until that break, the pattern remains "forming." V2 OHLCV's `close > consolidation_pivot` trigger is VCP-appropriate (volatility contraction breakout) and INAPPROPRIATE for W-bottom (which requires breaking through the midpoint resistance rather than the most-recent high).

**Entry**: Next-session open following the trigger close. Use the next-session-open from the OHLCV archive.

**Entry price**: `Open` of the next session after the close-above-center_peak session. If no next session exists in the archive (e.g., pattern triggers on the last available bar), pattern is "untriggered" — exclude from win/loss tally + count separately.

**Risk per trade**: Per `cfg.risk.max_risk_pct` (currently 0.005 = 0.5%); used for share-sizing calculation. Capital base: `max($7500 floor, actual_balance)` per CLAUDE.md "Capital risk floor convention" (operator memory note).

**Stop placement (initial)**: `trough_2_price * 0.99` (below the right trough by ~1% buffer; aligned with canonical W-bottom stop placement at the right shoulder low; do not use `min(trough_1_price, trough_2_price)` because the W's symmetry-violation undercut case sets `trough_2_price < trough_1_price` by design and using trough_2 is the strict definition).

**Trigger-search window**: from `data_asof_date + 1 trading day` (one session after the pattern was observed in the smoke) to `min(data_asof_date + 60 trading days, last_available_bar_in_archive)`. 60-day window mirrors V2 backtest precedent + matches typical W-bottom resolution timeframe.

---

## §3 Exit rulesets — 3 iterations

Run the FULL backtest 3 times — once per ruleset. Each iteration produces an independent win/loss/R-multiple distribution. (Mirrors V2 OHLCV backtest's 3-iteration structure for cross-comparison ease.)

### §3.1 Ruleset A — Minervini trail-MA (per `reference/methodology/`)

Per Minervini's Stage-2-uptrend exit guidance:
- **Initial stop**: `trough_2_price * 0.99` (as above).
- **Trail trigger**: when price extends >= +2R from entry. Pin exact threshold to reference text.
- **Trail rule**: once triggered, raise stop daily to `max(prior_stop, 21-day_SMA - 1*ATR)` (or similar; pin to reference).
- **Hard exit**: close <= 50-day SMA after entry (terminal stop regardless of trail state).
- **Trade window**: until either trail-stop OR hard-exit fires OR the archive ends.

### §3.2 Ruleset B — Fixed R-multiple

Mechanical: fire when unrealized P&L hits +3R OR -1R (initial stop).
- **Initial stop**: `trough_2_price * 0.99`.
- **Target**: entry_price + 3 * (entry_price - stop_price). Fires on first daily close at or above target.
- **Stop**: fires on first daily close below initial stop. No trail.
- **Trade window**: until target OR stop OR archive end.

### §3.3 Ruleset C — Close-below-50d-SMA

Per Disciplined Swing Trader reference + project precedent:
- **Initial stop**: `trough_2_price * 0.99`.
- **Trail rule**: NONE; initial stop never moves.
- **Hard exit**: first daily close below the candidate's 50-day SMA.
- **Trade window**: until initial stop OR 50d-SMA close-below OR archive end.

---

## §4 Output / analytical surface

### §4.1 Per-pattern per-ruleset CSV emission

`exports/research/double-bottom-w-backtest-<ISO>/results.csv` — one row per `(pattern, ruleset)` combination:

```
pattern_id, ticker, anchor_asof_date, trough_1_date, center_peak_price,
trough_2_price, composite_score, ruleset, triggered, entry_session,
entry_price, initial_stop_price, exit_session, exit_price, exit_reason,
trade_pnl_R, trade_pnl_dollars, peak_unrealized_R, drawdown_to_exit_R,
trade_duration_sessions
```

24 columns total (matches the pattern_cohort_evaluator output shape for downstream tooling consistency).

### §4.2 Per-ruleset analytical markdown summary

`exports/research/double-bottom-w-backtest-<ISO>/summary.md` — sections:
- Headline: per-ruleset win/loss counts + R-multiple distribution (mean / median / std) + Sharpe-like ratio (mean_R / std_R)
- Per-ticker breakdown: which patterns triggered? Which won? Which lost? Time-to-resolution distribution.
- Per-composite-score-bucket: composite>=0.9 vs 0.7-0.9 — does higher composite predict higher win rate?
- Per-template-match-score-bucket: template_match_score is None vs populated — does template confirmation predict outcome?
- Comparison vs V2 OHLCV backtest at `e0a9edd`: 29% triggered / -0.18R mean unrealized (across-arc baseline).

### §4.3 Manifest JSON

`exports/research/double-bottom-w-backtest-<ISO>/manifest.json` — cohort SHA-256 + ruleset count + per-ruleset patterns_count + runtime + L2 LOCK sentinel + V1 source-ladder consistency check.

---

## §5 Discriminating tests (~16-20 fast tests)

At `tests/research/test_double_bottom_w_backtest_*.py`:

### §5.1 Cohort fixture construction (4-5 tests)

- Parse `results.csv` filtered to composite>=0.7 double_bottom_w; assert 725 rows (or whatever the live count is + log delta).
- Deduplicate to unique patterns; assert pattern count in expected range [10, 30].
- Per-pattern: verify center_peak_price > both trough prices; verify trough_2_date > trough_1_date.
- Per-pattern: extract from results.csv vs reconstruct from primary verdict's structural_evidence_json; assert byte-identical.

### §5.2 Entry-rule trigger detection (4-5 tests)

- Synthetic pattern with known center_peak_price + plant 60 bars of synthetic OHLCV with one bar's Close > center_peak_price; assert trigger detected.
- Synthetic pattern with NO bar above center_peak; assert untriggered.
- Synthetic pattern with multiple bars above center_peak; assert FIRST one detected (not last).
- Trigger search window respects `data_asof_date + 1 day` boundary (don't fire on pre-asof bars).
- Trigger detection respects the 60-day max window.

### §5.3 Exit-ruleset application (6-7 tests; ~2 per ruleset)

- Ruleset A trail-MA: synthetic +2R move; assert trail triggers; assert stop raises; assert subsequent close-below-trail fires exit.
- Ruleset B fixed R: synthetic +3R close; assert exit at target. Synthetic -1R close; assert exit at stop.
- Ruleset C 50d-SMA: synthetic close-below-50d; assert exit at that close.

### §5.4 R-multiple calculation (2 tests)

- Long entry at $100; stop at $99; exit at $103; assert trade_pnl_R = +3.0 (target hit).
- Long entry at $100; stop at $99; exit at $98.50; assert trade_pnl_R = -1.5 (stop overshoot).

### §5.5 L2 LOCK BINDING (2 tests; mirror pattern_cohort_evaluator)

- Module-import-graph sentinel: assert NO `yfinance` / `schwabdev` / `swing.integrations.schwab` import paths reach the backtest module.
- File-open boundary spy: assert OHLCV reads route through `swing.data.ohlcv_archive.read_or_fetch_archive` ONLY (or equivalent V1 read path).

---

## §6 Watch items + cumulative discipline (BINDING)

### §6.1 Cumulative discipline (29 gotchas; pre-Codex 12-expansion BINDING)

If Codex MCP review invoked, ALL 29 gotchas BINDING for 38th cumulative C.C lesson #6 validation. **ESPECIALLY relevant to this backtest**:

- **#26** — archive bar-content TEMPORAL mutation: forward-walked bars from CURRENT archive may differ from contemporaneous V1 state. Document caveat in findings.
- **#28 + #29** — exemplar OHLCV cache discipline: backtest doesn't load exemplars (pattern_exemplars table not consumed by backtest), so DIRECTLY exempt; but the FORWARD-walk OHLCV reads from `prices-cache` (hyphen) per L8 lesson.
- **#23 + #22** — dataclass attribution metadata + per-counter-accumulation: per-pattern per-ruleset emit MUST attribute each row by (pattern_id, ruleset) NOT by value-matching; per-ruleset counters increment per-pattern not per-window.
- **T2.SB5 "Bad-exemplar isolation"** — extends to "per-pattern isolation": if one pattern's OHLCV read fails (e.g., delisted ticker / archive missing), continue with the other patterns; record per-pattern failure in skip-reason counter.

### §6.2 Per-dispatch watch items

- (a) **L2 LOCK BINDING preservation** — no new schwab/yfinance imports; all OHLCV reads via existing V1 read path.
- (b) **ASCII-only on all narrative outputs** (summary.md + findings.md) — operator's cp1252 encoder rejects unicode glyphs per cumulative gotcha.
- (c) **ZERO production swing/ writes** — backtest is research-only; new code at `research/harness/double_bottom_w_backtest/` only.
- (d) **CLI carve-out** — if a CLI surface is needed, mirror OQ-13 pattern (add minimal `swing diagnose double-bottom-w-backtest` subcommand at `swing/cli.py`; budget ~30-50 lines; document in return report).
- (e) **Schema v21 unchanged** — no migrations.
- (f) **Pattern-level vs window-level emit discipline** (cumulative gotcha #22 + Expansion #8 promoted scope): per-ruleset COUNTERS accumulate per-PATTERN (not per-window). 725-window cohort collapses to ~10-30 patterns; emit 10-30 * 3 ruleset = ~30-90 result rows total.
- (g) **Trigger-search-window-boundary discipline** — `data_asof_date + 1 day` lower bound + 60 days OR archive end upper bound; do NOT walk backward from data_asof_date.

### §6.3 Cross-comparison with V2 OHLCV backtest (`e0a9edd`)

The V2 backtest's findings document (`docs/v2-tightness-range-factor-backtest-findings-2026-05-24.md`) reports:
- 17 patterns / 5 triggered (29% rate) / 0 closed / -0.18R mean unrealized across 5 open positions
- All 3 exit rulesets emitted IDENTICAL pattern-level outcomes (post-trigger divergence never fired because no trade closed)
- Cohort baseline 0.67: 2 patterns / 1 triggered (50% rate) / 1 open

The D1 backtest SHOULD produce different results because:
- Different trigger rule (W-bottom-appropriate)
- Different cohort filter (composite>=0.7 double_bottom_w vs all 67 cohort entries via VCP detector)
- Same forward bars + same archive + same exit rulesets

Implementer findings section MUST cross-tabulate against V2 backtest:
- Per-ticker overlap: which of the 15 V2 backtest tickers also appear in D1 cohort?
- Per-pattern overlap: which V2 patterns correspond to D1 patterns? (cross-anchor cohort_entry_id)
- Per-outcome: D1 trigger rate vs V2 29%? D1 trade closure rate vs V2 0%? D1 mean-R vs V2 -0.18R?

### §6.4 Codex MCP decision

OPERATOR-PAIRED PRE-DISPATCH decision per the per-dispatch cumulative discipline. Recommendation: invoke Codex MCP adversarial review if:
- New analytical modules cumulatively land >200 lines (likely YES — backtest engine is substantial; new exit-rule helpers; new cohort fixture loader);
- Operator wants the 38th cumulative C.C lesson #6 validation slot fired NOW;
- The cohort dedup logic surprises the implementer (high cognitive complexity warrants adversarial check).

Operator may choose to defer Codex to a follow-up dispatch OR fire it here.

---

## §7 Acceptance criteria

### §7.1 Functional

- [ ] `results.csv` has 24 columns per spec; row count = unique_pattern_count * 3 rulesets.
- [ ] Each pattern's entry trigger respects `data_asof_date + 1 day` lower bound + 60-day max upper bound + center_peak_price trigger threshold.
- [ ] Each ruleset's exit logic matches reference text (Minervini for A; mechanical for B; Disciplined Swing Trader for C).
- [ ] Per-pattern R-multiple computed correctly (entry - exit - shares scaled by initial-stop distance).
- [ ] Manifest `l2_lock_preserved: true`.

### §7.2 Test scope

- [ ] 16-20 NEW fast tests at `tests/research/test_double_bottom_w_backtest_*.py`.
- [ ] All existing tests still green (baseline ~5976 fast tests post-Turn-F-bug-#2-fix; this dispatch adds ~16-20 → ~5992-5996).
- [ ] `python -m pytest tests/research/ -m "not slow" -q` exits 0 with new tests.
- [ ] Broader fast suite `python -m pytest -m "not slow" -q` exits 0.

### §7.3 Discipline preservation

- [ ] ZERO Co-Authored-By footer drift (preserve ~530+ cumulative streak through `bbe0a0b`).
- [ ] ZERO production swing/ writes beyond OQ-13-mirror CLI carve-out (if needed; budget ~30-50 lines).
- [ ] Schema v21 unchanged.
- [ ] ZERO new Schwab API calls (L2 LOCK preserved + REINFORCED).
- [ ] ASCII-only on summary.md + findings.md.

### §7.4 Analytical deliverables

- [ ] `exports/research/double-bottom-w-backtest-<ISO>/` artifact directory created with results.csv + summary.md + manifest.json (mirrors pattern_cohort_evaluator output shape).
- [ ] `docs/pattern-cohort-double-bottom-w-backtest-findings-<ISO>.md` — analytical narrative (mirrors V2 OHLCV backtest findings doc shape; cite study writeup R1 hypothesis verbatim; report verdict POSITIVE / NEGATIVE / INCONCLUSIVE per criterion in §7.5 below).
- [ ] Cross-tabulation vs V2 OHLCV backtest at `e0a9edd` per §6.3 — per-ticker overlap + per-pattern overlap + per-outcome comparison.

### §7.5 Verdict classification

- **POSITIVE**: D1 trigger rate substantially higher than V2's 29% (>=50%) AND mean-R across all 3 rulesets positive (>0R) AND at least 1 ruleset shows multiple closed-and-profitable trades. Implication: the R1 hypothesis confirmed; chart-shape-appropriate trigger rules unlock real expectancy.
- **NEGATIVE**: D1 trigger rate <= V2's 29% OR mean-R <= -0.5R OR 0 closed-and-profitable trades. Implication: the R1 hypothesis falsified; chart-shape detection is necessary but insufficient for actionable trading.
- **INCONCLUSIVE**: trigger rate 30-50% AND mean-R between -0.5R and 0R AND at least one closed-and-profitable trade. Implication: cohort sample size insufficient; recommend (R2) per-variable cohort expansion before deployment decision.

---

## §8 Commit cadence + return report

### §8.1 Commit cadence

TDD slice discipline (~10-15 commits):
1. Cohort fixture loader test (RED) + impl (GREEN)
2. Entry-rule trigger detector test (RED) + impl (GREEN)
3. Per-ruleset exit detector tests (one commit per ruleset; 6 commits)
4. R-multiple calculator test + impl
5. Cohort dedup test + impl
6. End-to-end backtest runner test + impl
7. Output emitter (CSV / summary / manifest) — 1-3 commits
8. CLI wiring (if applicable) — 1 commit (OQ-13-mirror carve-out)
9. Smoke artifact generation + commit
10. Findings doc + return report

Mirrors V2 OHLCV backtest's commit cadence (16 commits; ~16 fast tests).

### §8.2 Return report

Author at `docs/pattern-cohort-double-bottom-w-backtest-return-report.md`. Sections:
- §0 TL;DR (verdict per §7.5)
- §1 Commits summary (per-task table)
- §2 Tests added + tests preserved
- §3 Smoke artifact verification + summary highlights
- §4 Discipline preservation (Co-Authored-By streak + L2 LOCK + production scope + schema lock + ASCII)
- §5 Banked V2 candidates (e.g., bootstrap confidence intervals; sector stratification; Stage 3 AI second-opinion eval if positive verdict)
- §6 Discipline deviations BANKED (any consolidation deviations from §8.1 cadence)
- §7 Codex MCP invocation status (per pre-dispatch decision; document chain + 38th cumulative validation outcome if invoked)
- §8 Cross-tabulation with V2 OHLCV backtest at `e0a9edd`
- §9 R1 hypothesis verdict + implications for R2 (other 4 VCP-family binding variables) + R3 (treat sensitivity analysis as upstream diagnostics)

---

## §9 Branch + worktree setup

```powershell
# From the repo root:
git checkout main
git pull origin main
git worktree add .worktrees/applied-research-pattern-cohort-double-bottom-w-backtest -b applied-research-pattern-cohort-double-bottom-w-backtest
cd .worktrees/applied-research-pattern-cohort-double-bottom-w-backtest
# Verify branch + working tree are clean
git status
git log --oneline -5
# Work begins from here. Use `python -m swing.cli` (NOT bare `swing`).
```

When done:
- Push branch: `git push -u origin applied-research-pattern-cohort-double-bottom-w-backtest`
- Author findings doc + return report
- Open a PR (or notify orchestrator for merge) — orchestrator performs the merge per `feedback_orchestrator_performs_merge` BINDING

---

## §10 Do NOT

- Modify production `swing/` beyond an OQ-13-mirror CLI carve-out (if needed; budget ~30-50 lines for `swing diagnose double-bottom-w-backtest`)
- Modify V1 persisted state
- Trigger Schwab API calls (L2 LOCK BINDING + REINFORCED via 5 existing pattern_cohort_evaluator + V2 OHLCV reader tests)
- Modify any schema (v21 LOCKED)
- Pre-fetch additional OHLCV data via yfinance — the cohort + forward-walk uses EXISTING archive only (per L2 LOCK + V1 read path consistency)
- Add Co-Authored-By footer to ANY commit
- Skip the §6.3 V2 OHLCV backtest cross-tabulation — that's the comparative dataset
- Verdict the result as "positive" without the §7.5 criteria being met (POSITIVE requires trigger rate >=50% AND mean-R >0R AND at least 1 ruleset with multiple closed-and-profitable trades — all three; partial conditions = INCONCLUSIVE or NEGATIVE)
- Use `pivot_price` from DoubleBottomWEvidence as the trigger threshold — it's the last close in the candidate window (per `swing/patterns/double_bottom_w.py:594`) and NOT actionable; use `center_peak_price` instead

---

*End of dispatch brief. Substantial research-only walk-forward backtest study; tests the Turn F B study writeup's R1 hypothesis (chart-shape-appropriate trigger rule unlocks W-bottom cohort expectancy); preserves all cumulative discipline streaks; cross-tabulates against V2 OHLCV backtest at `e0a9edd` for arc-coherence.*
