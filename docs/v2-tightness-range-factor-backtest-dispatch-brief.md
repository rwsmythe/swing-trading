# V2 `vcp.tightness_range_factor=1.005` Walk-Forward Backtest Study — Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the V2 `vcp.tightness_range_factor` walk-forward backtest study implementer. No prior conversation context.

**Mission:** Take the ~67-75 candidates that flip into `aplus` at `vcp.tightness_range_factor=1.005` (per the V2 OHLCV sensitivity matrix headline) and run a walk-forward backtest to determine **win/loss outcome + R-multiple distribution** under **3 exit rulesets**: Minervini trail-MA, fixed R-multiple, and close-below-50d-SMA. This bridges the V2 sensitivity arc's "which dial is binding" answer (current: top binding variable `vcp.tightness_range_factor` +75 max_delta_aplus) to the substantive "does loosening it generate profitable trades" question that gates cfg-policy proposal per V2.1 §VII.C.

**Workflow:** `superpowers:test-driven-development` skill (study-scoped; reproducible-fixtures pattern). Adversarial Codex MCP review OPTIONAL — invoke if new analytical modules land beyond ~200 lines.

**Branch:** `applied-research-v2-tightness-range-factor-backtest` — branches from main HEAD `f7157c3` (or later; reflects D1 SHADOW promotion + D2 study writeup amendment).

**Worktree:** `git worktree add .worktrees/applied-research-v2-tightness-range-factor-backtest applied-research-v2-tightness-range-factor-backtest`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~4-8 hours operator-paced. New analytical surface (walk-forward backtest engine; not in existing research/ harness).

---

## §0 Read first (in this order)

1. **`research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md`** — the study this backtest extends. Especially Per-variable findings table + Amendment 2 (5 binding variables; `vcp.tightness_range_factor` leading at +75 max_delta_aplus).

2. **`exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`** — full-reproduction smoke artifact. **Per-variable drill-down section `### vcp.tightness_range_factor` at lines 9725-10866** contains the per-candidate flip enumeration for the +75 / +67 backtest population.

3. **`research/method-records/aplus-criteria-calibration.md`** (v0.3.0 SHADOW) — method-record. Especially `## Known limitations of V2 baseline-parity claims` §"Limitation L6" (archive bar-content TEMPORAL mutation; the backtest must address this since it walks forward through current archives).

4. **`reference/methodology/`** — Minervini + Disciplined Swing Trader reference texts for exit-rule semantics (operator's source-of-truth). Especially Minervini's trail-MA / Stage-2-uptrend exit rules.

5. **`swing/trades/`** — production exit-advisory rule implementations (`stop_adjust.py`, `advisory.py`, `daily_management.py`). Useful for matching V1 production exit logic; backtest implementation should mirror.

6. **`swing/evaluation/criteria/vcp.py`** — VCP detection criteria. Especially the tightness-range-factor + tightness-days computation + the consolidation_low + consolidation_high pivot identification (the pivot price comes from `consolidation_high`).

7. **`swing/data/ohlcv_archive.py`** (`read_or_fetch_archive`) — V1's read path. Backtest walk-forward must use the same path to maintain L2 LOCK consistency (legacy parquet read; ZERO Schwab API calls; ZERO yfinance calls).

8. **CLAUDE.md** gotchas — especially #25 + #26 (parity-comparison discipline; archive mutation). Backtest is forward-looking from each candidate's `data_asof_date` so L6 mutation primarily affects pivot identification, not forward path; document caveat.

---

## §1 Backtest population — candidate list

**Source:** drill-down section `### vcp.tightness_range_factor` (lines 9725-10866 of the full-reproduction smoke artifact). Filter to rows with `sweep_point=1.005` AND `to_bucket=aplus`. Implementer task §3.1 is to extract verbatim.

**Pre-extracted summary** (orchestrator-side; for sanity-check at fixture construction):

| Ticker | Eval-run count | Eval-run IDs |
|---|---|---|
| RLMD | 12 | 13, 14, 15, 16, 17, 18, 29, 30, 33, 42, 43, 44 |
| DNTH | 10 | 12, 13, 14, 15, 16, 17, 18, 19, 20, 21 |
| RNG | 9 | 22, 23, 24, 25, 26, 27, 28, 29, 30 |
| KOD | 8 | 25, 26, 27, 28, 29, 30, 31, 32 |
| YOU | 7 | 22, 23, 24, 55, 56, 57, 64 |
| FRO | 6 | 19, 20, 21, 22, 23, 24 |
| TROX | 4 | 25, 26, 27, 28 |
| PTEN | 2 | 40, 41 |
| OII | 2 | 9, 10 |
| DK | 2 | 53, 54 |
| WULF | 1 | 52 |
| UCTT | 1 | 44 |
| TSHA | 1 | 45 |
| SSRM | 1 | 52 |
| NAT | 1 | 44 |
| **Total** | **67** | **15 unique tickers** |

**Discrepancy with matrix +75 figure**: Matrix `delta_aplus[sweep_point=1.005] = 75` (aplus_count 5→80; net delta +75). Drill-down enumerates 67 `watch→aplus` flips. Discrepancy of 8 may be: (a) baseline-aplus candidates whose bucket stays aplus + doesn't appear in flip records; (b) flips from non-watch source buckets (skip→aplus or other) not captured by drill-down's filter; (c) V2-recomputed-baseline-map vs V1-persisted state delta (per L6). Implementer task §3.1 includes verifying the discrepancy at fixture-construction time + documenting in findings.

**Pattern-level deduplication**: Consecutive eval_runs per ticker likely represent the **same VCP pattern** persisting across sessions. The 67 entries collapse to roughly **15 unique VCP patterns** (one per ticker; or possibly 2-3 patterns per ticker if there's a sufficient gap between eval_run clusters — e.g., RLMD's 13-18 cluster vs 29-30 cluster vs 33 vs 42-44 cluster may be distinct patterns). Implementer task §3.2: group consecutive eval_runs (within ~5 trading days) into single "patterns"; report unique pattern count + per-pattern entry/exit/outcome.

---

## §2 Entry rule

**Trigger**: First daily close > pivot price (where pivot = `consolidation_high` from V2 evaluator output at the FIRST eval_run in the pattern group).

**Entry**: Next-session open following the trigger close. Use the next-session-open from the OHLCV archive.

**Entry price**: `Open` of the next session after the close-above-pivot session. If no next session exists in the archive (e.g., pattern triggers on the last available bar), pattern is "untriggered" — exclude from win/loss tally + count separately.

**Risk per trade**: Per `cfg.risk.max_risk_pct` (currently 0.005 = 0.5%); used for share-sizing calculation. Capital base: `max($7500 floor, actual_balance)` per CLAUDE.md "Capital risk floor convention" (operator memory note).

**Stop placement (initial)**: Per Minervini reference + project precedent — set initial stop at consolidation_low (or `consolidation_low * 0.99` for buffer; implementer to pin via reference reading). This stop applies under ALL 3 exit rulesets (only the TRAIL/UPDATE behavior differs).

---

## §3 Exit rulesets — 3 iterations

Run the FULL backtest 3 times — once per ruleset. Each iteration produces an independent win/loss/R-multiple distribution.

### §3.1 Ruleset A — Minervini trail-MA (per `reference/methodology/`)

Per Minervini's Stage-2-uptrend exit guidance:
- **Initial stop**: consolidation_low (as above).
- **Trail trigger**: when price extends ≥ +2R from entry (or similar threshold; pin to reference text).
- **Trail mechanism**: trail stop to 10-week (50-day) SMA after trigger; ratchet up only.
- **Hard exit**: close below 50-day SMA after trail trigger fires.
- **Reference**: `reference/methodology/` Minervini text — implementer pins exact threshold from reference reading.

### §3.2 Ruleset B — Fixed R-multiple

- **Initial stop**: consolidation_low (as above).
- **Stop-to-breakeven**: at +1R unrealized.
- **Target exit**: +3R OR trail-stop hit (whichever fires first).
- **Trail mechanism (post-breakeven)**: optional — pin to one of (a) trail at half-R below current price; (b) trail at 21-day SMA; (c) no further trail after BE. Recommend (b) for consistency with project precedent.
- **Hard exit**: stop hit OR +3R target hit OR data-tail reached.

### §3.3 Ruleset C — Close-below-50d-SMA

Simplest Stage-2 stop rule:
- **Initial stop**: consolidation_low.
- **Trail trigger**: when price closes above 50-day SMA + 50-day SMA is rising.
- **Trail mechanism**: trail stop to 50-day SMA on close.
- **Hard exit**: first daily close below 50-day SMA after trail fires.

---

## §4 Walk-forward execution

For each (pattern, ruleset) tuple:

1. Identify entry trigger date (first close > pivot after eval_run asof_date).
2. Compute entry price (next-session open).
3. Compute initial stop (consolidation_low at pattern asof_date).
4. Compute share count via `swing.recommendations.compute_shares` (or equivalent inline calculation).
5. Walk forward through OHLCV bars; apply ruleset's stop-update + exit logic.
6. Record: entry_date, entry_price, exit_date, exit_price, exit_reason, R-multiple realized, dollar P&L, days held.

**Data tail handling**: if pattern doesn't exit by 2026-05-22 (last available bar), record as `open_position` with current-price-relative R-multiple + days held. Include in aggregate stats but flag separately.

**Compounding vs fixed-capital**: use **fixed-capital** per trade (each trade sized against initial capital independently; no compounding). Simpler analytical baseline; compounding can be V2 candidate.

---

## §5 Deliverables

1. **Per-pattern per-ruleset results CSV** at `exports/research/tightness-range-factor-backtest-<ISO>/results.csv`:
   - Columns: pattern_id (ticker + first_eval_run), ticker, entry_date, entry_price, initial_stop, exit_date, exit_price, exit_reason, ruleset, R-multiple, dollar_pnl, days_held, status (closed / open).

2. **Aggregate stats table** in markdown at `exports/research/tightness-range-factor-backtest-<ISO>/summary.md`:
   - Per ruleset: total_patterns, winners, losers, untriggered, open_position, win_rate, avg_R_winner, avg_R_loser, expectancy_R, avg_days_held, max_drawdown.
   - Cross-ruleset comparison table.
   - Control: same backtest run on the **baseline 5 A+ candidates** from the smoke (the 5 candidates that ARE aplus at `vcp.tightness_range_factor=0.67`). Compare baseline-cohort vs loosened-cohort expectancy.

3. **Study writeup amendment** to `research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md`: append `## Walk-forward backtest validation (vcp.tightness_range_factor=1.005)` section with the aggregate stats + cross-ruleset comparison + conclusion (does loosening tightness_range_factor produce net-positive trading edge?).

4. **Findings document** at `docs/v2-tightness-range-factor-backtest-findings-<DATE>.md`:
   - Population characterization (15 unique tickers; consolidation patterns; sector concentration).
   - Per-ruleset per-pattern outcome table.
   - Expectancy + win-rate analysis.
   - L6 caveat (archive mutation affects pivot identification — pivots used are from CURRENT archive; document the L6 limitation impact on backtest fidelity).
   - Sensitivity: does the +/-1 R-multiple bound on initial stop change the aggregate verdict? (robustness check).
   - Comparison with baseline 5 cohort.

5. **Return report** at `docs/v2-tightness-range-factor-backtest-return-report.md`.

---

## §6 Watch items + cumulative discipline (BINDING)

### §6.1 Cumulative discipline (26 gotchas)

If backtest engine code is non-trivial (≥200 lines analytical surface) AND Codex review is invoked, ALL 26 cumulative CLAUDE.md gotchas (1-26) BINDING for any 36th cumulative C.C lesson #6 validation.

### §6.2 Process discipline

- **NO Co-Authored-By footer** — ~508+ cumulative streak through `f7157c3`; preserve
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`
- **ASCII-only on runtime CLI paths** + markdown narrative
- **TDD per task** (each ruleset's stop-update + exit logic gets its own discriminating test set)
- **Edit tool for per-file edits**

### §6.3 Schema discipline (LOCK)

Schema v21 LOCKED. Backtest MUST NOT touch migrations.

### §6.4 L2 LOCK preservation (BINDING)

ZERO new Schwab API calls. Backtest reads ONLY from `~/swing-data/prices_cache/` legacy parquet files (same source as V2 reader per L2 LOCK). 14 BINDING reader-tests MUST remain green if backtest engine lands in `research/harness/`.

### §6.5 Read-only invariant for V1 persisted state

Backtest is forward-walking simulation. ZERO modification of `candidate_criteria` / `candidates` / `evaluation_runs` / `trades` / any V1-persisted-state table.

### §6.6 Production swing/ read-only EXCEPT existing OQ-17 carve-out

`git diff main -- swing/` MUST remain empty (V2 ship already includes `swing/cli.py` +71 lines for OQ-17 carve-out; backtest MUST NOT add to swing/). Backtest engine lands under `research/` or as inline analysis scripts under `tmp/`.

### §6.7 L6 caveat in findings

Backtest pivot identification reads CURRENT archive (per L6 architectural limitation; same as V2 sensitivity sweep). Document the L6 caveat explicitly in findings — pivots may differ slightly from what V1 saw at pattern asof_date, but the forward-walking exit semantic is more robust to this drift than the criterion bucket comparison (forward simulation operates on the same archive consistently; only the entry trigger may shift if the close-above-pivot crossing date moved due to bar mutation).

---

## §7 NON-scope

- ZERO production swing/ writes beyond existing OQ-17 carve-out
- ZERO new Schwab API calls (L2 LOCK preserved)
- ZERO modification of V1 persisted state
- ZERO new schema migrations
- ZERO Phase 14 commissioning consideration (DEFERRED per Path B sequencing)
- ZERO cfg-policy proposal authoring (this study's OUTPUT informs the cfg-policy proposal; the proposal itself is a SEPARATE follow-up)
- ZERO 2D / interaction-term sweep (V3+ per V2.1 §IV.B)
- ZERO bootstrap-resampling / Monte Carlo (banked V2 candidate; this study is a single-pass walk-forward)
- ZERO position-sizing analysis beyond fixed-capital per-trade (compounding banked V2 candidate)
- ZERO sector / regime stratification beyond the report-level table (banked V2 candidate)

---

## §8 Post-study handback

When backtest + study writeup amendment + return report shipped:

1. Write findings document at `docs/v2-tightness-range-factor-backtest-findings-<DATE>.md`
2. Write return report at `docs/v2-tightness-range-factor-backtest-return-report.md`
3. Amend `research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md` with new section
4. Inline self-verification: ruff check (if code changes); schema unchanged; ZERO new Schwab API calls; ZERO Co-Authored-By footer; V1 persisted state unchanged
5. Hand back to operator with: per-ruleset aggregate stats summary; cross-ruleset comparison; verdict (does loosening tightness_range_factor produce net-positive edge?); L6 caveat impact assessment; next-step recommendation (cfg-policy proposal substrate IF verdict positive; OR pivot to different binding variable IF verdict negative).

Orchestrator-side next steps post-handback:
- QA findings per `feedback_orchestrator_qa_implementer_product`
- Merge backtest branch `--no-ff` to main; push
- Post-merge housekeeping (sub-event scale; in-place amendments)
- Operator-paired decision on cfg-policy proposal authoring (if backtest verdict positive) OR pivot to alternative binding variable backtest (e.g., `vcp.tightness_days_required` +16; the next-most binding)

---

## §9 Open questions to flag if encountered

- Pivot identification: should pivot use `consolidation_high` from the FIRST eval_run in a pattern group, OR the LAST (most recent before entry trigger)? Default to FIRST per the V2 sensitivity sweep's per-eval-run granularity; flag if implementer finds material difference.
- Trail mechanism in Ruleset B post-breakeven: which sub-option (a / b / c per §3.2)? Default to (b) 21-day SMA per consistency with Minervini family; flag if reference reading suggests alternative.
- Pattern-grouping window: ~5 trading days proposed for collapsing consecutive eval_runs into a single pattern. Flag if material pattern-count change at 3 vs 10 day windows.
- Untriggered patterns: do they enter the per-ruleset denominator (drag on win-rate) or only the separate untriggered-count? Default to SEPARATE (clean win-rate excludes untriggered); document both interpretations.
- L6 archive-mutation impact on backtest fidelity: document but do NOT attempt to remediate (immutable-archive-snapshot is V2.5/V3 candidate; out of scope).

---

*End of V2 `vcp.tightness_range_factor=1.005` walk-forward backtest study dispatch brief. Population ~67 candidates (15 unique tickers; ~15-25 unique VCP patterns after consecutive-eval-run dedup); 3 exit rulesets (Minervini trail-MA / Fixed R-multiple / Close-below-50d-SMA); ~4-8 hours operator-paced. Deliverable = per-ruleset aggregate stats + cross-ruleset comparison + study writeup amendment + verdict on cfg-policy proposal substrate. ~508+ ZERO Co-Authored-By footer streak preserved through this brief commit. Study bridges V2 sensitivity arc to cfg-policy proposal pathway per V2.1 §VII.C shadow → production lifecycle.*
