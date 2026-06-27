# G2 W-Bottom-Derived Ruleset Backtest -- Return Report

**Implementer branch:** `applied-research-g2-w-bottom-ruleset-backtest`
**Dispatch brief:** `docs/g2-w-bottom-ruleset-backtest-dispatch-brief.md` (main commit `423f21d`; amended in-place via Brief Amendments 1-4 banked during Codex MCP pre-smoke chain)
**Findings doc:** `docs/g2-w-bottom-ruleset-backtest-findings-20260527.md`
**Smoke artifact:** `exports/research/g2-w-bottom-ruleset-backtest-20260527T213434Z/`

**Substrate SHAs (gotcha #35 + reproducibility):**
- R2-A canonical N=65: `758675b897affb4cf779259fdfe41398a3305b9480e8e3e510a358d83c4a35e7` (window 21d)
- D2 EXPANDED N=42: `9075ac66d70401a19f11c06b681d859d3a5fbcd16e373e282c4db991bd6cc40c` (window 31d; Brief Amendment 1; brief stated N=71 stale)

---

## Sec 1 Dispatch outcome

**SHIPPED end-to-end (Slices 0-8 complete; both Codex MCP chains CONVERGED).** 9-ruleset x 2-substrate G2 W-bottom-derived ruleset backtest complete; 9-metric scorecard emitted with descriptive narrative; gotcha #33 banned-verdict-terms LOCK preserved throughout; gotcha #35 prior-arc-anchor citation discipline FIRST CANONICAL APPLICATION shipped (substrate SHAs + metric formulas at every prior-arc citation).

**Joint hypothesis (H_joint) NOT supported at the tested substrate scale.** All 9 rulesets show expectancy_R below zero on both R2-A (N=65) and D2 EXPANDED (N=42) substrates. G_bulkowski's tight-trough_2 stop achieves a substantive avg_loss_R reduction (1.55R -> 0.62R on R2-A) but does not produce expectancy_R > 0 at this substrate size. The 9-metric scorecard surfaces SUBSTANTIVE diagnostic substance (which stop convention reduces per-loss magnitude; volume gating selectivity-vs-conversion trade-off; D2 substrate-freshness sensitivity).

---

## Sec 2 Slice-by-slice ship summary

| Slice | Deliverable | Status | Commit |
|---|---|---|---|
| 0 | Recon (existing harness + fixtures + scorecard precedents) | DONE (no commit; pre-impl analysis) | - |
| 1 | g2 package scaffolding + walkforward_ghi + G_bulkowski + 14 tests | SHIPPED | `d487761` |
| 2 | H_oneil_double_bottom_base + 10 tests | SHIPPED | `0144680` |
| 3 | I_edwards_magee_classical + 10 tests | SHIPPED | `6adb133` |
| 4 | scorecard.py 9-metric + 14 tests | SHIPPED | `a0575b7` |
| 5a | run.py orchestrator + io.py emitters + 47 lock+orchestrator tests | SHIPPED | `a3fb351` |
| 5b | Codex MCP pre-smoke chain R1-R5 (CONVERGED) | SHIPPED | `9626d84` + `ed3e2d9` + `9b5b263` + `901b9ea` + `63228d3` + `5f15aeb` |
| 5c | Smoke artifact + .gitignore exception | SHIPPED | `267ed25` |
| 6 | Findings doc + return report initial draft | SHIPPED | `48a5f82` |
| 7 | Codex MCP post-smoke chain R6-R7 (CONVERGED) | SHIPPED | `bb7ddec` + `fe4dada` |
| 8 | Return report finalization (this slice) | THIS commit | - |

Total commits through Slice 8: 15 implementer commits + 1 dispatch brief = 16 commits on branch.

---

## Sec 3 Deliverables shipped

### Sec 3.1 NEW research/harness/g2_w_bottom_ruleset_backtest/ package (7 modules + 8 test files)

- `__init__.py` -- package marker + docstring
- `rulesets/__init__.py` -- per-file ruleset package marker
- `rulesets/g_bulkowski_double_bottom.py` -- RulesetG class + bulkowski_trigger_predicate function
- `rulesets/h_oneil_double_bottom_base.py` -- RulesetH class + oneil_trigger_predicate function
- `rulesets/i_edwards_magee_classical.py` -- RulesetI class + edwards_magee_trigger_predicate function
- `walkforward_ghi.py` -- NEW engine variant with DeferredExit + GhiRuleset Protocol + walk_forward_with_trigger_predicate + find_trigger_index_with_predicate
- `scorecard.py` -- ScorecardRow dataclass (16 fields) + build_scorecard_row function + write_scorecard_csv emitter
- `io.py` -- artifact emitters (write_manifest + write_summary_markdown + write_narrative_synthesis_markdown + write_per_trade_detail_csv)
- `run.py` -- main() orchestrator: loads R2-A + D2 substrates; runs A-F (existing walk_forward) + G/H/I (walk_forward_with_trigger_predicate); emits 5-file smoke artifact

### Sec 3.2 NEW tests/research/g2_w_bottom_ruleset/ test suite (113 fast tests + 1 self-skip)

- `__init__.py` -- empty package marker
- `test_walkforward_ghi.py` -- 7 engine tests (legacy parity + final-bar trigger + entry-at-trigger-bar semantic + predicate-rejects-first-admits-second + non-callable raises TypeError + predicate signature)
- `test_ruleset_g_bulkowski.py` -- 11 RulesetG tests (initial_stop arithmetic; NO entry-relative arm discriminator; pattern-anchored target arithmetic; t1<t2 case; target exit on first close>=target; DeferredExit emit on stop; full-engine next-bar-open path; full-engine data-tail fallback; volume predicate 1.2x/1.3x-strict/1.31x; insufficient-history rejection; full end-to-end target_measured_move exit)
- `test_ruleset_h_oneil.py` -- 10 RulesetH tests (initial_stop entry-relative; trough_2-independence discriminator; pattern-anchored target arithmetic; target exit; DeferredExit on stop; close_below_50d on SMA50 break; stop_hit precedence over close_below_50d same-bar; predicate 1.3x/1.4x-strict/1.41x; insufficient-history rejection; full end-to-end target_measured_move exit)
- `test_ruleset_i_edwards_magee.py` -- 10 RulesetI tests (initial_stop lower-trough; t1<t2 + t2<t1 cases; discriminator vs G; pattern-anchored target arithmetic; target exit; DeferredExit on stop; predicate rally-volume-baseline 1.4x/1.5x-strict/1.6x; predicate falls through no-rally-bars; full end-to-end target_measured_move exit; throwback single-entry semantic)
- `test_scorecard.py` -- 14 scorecard tests (expectancy_R discriminator vs buggy formula; 0 closed; 0 triggered; 0 losses; 0 winners; open_at_tail count semantic; estimated_dollar derivation; None expectancy passthrough; substrate_window=0 edge case; trigger_conversion denominator; median_time only closed trades; 16-field shape; per-ruleset filtering; admin sentinel filtering; open_at_tail_rate derivation; zero-triggered rate=None)
- `test_run_orchestrator.py` -- 5 orchestrator tests (9 rulesets per verdict; D2 EXPANDED filter; full main() artifact bundle; narrative banned-verdict-terms; OhlcvCoverageError graceful degradation)
- `test_locks.py` -- 41 discipline-locking tests + 1 self-skip (L2 LOCK source-grep per G2 file; ASCII discipline per G2 file; cohort fixture SHA byte-stability; A-F harness SHA byte-stability; gotcha #33 production-code banned-term grep; gotcha #33 summary.md emitter scan; gotcha #35 narrative + summary emitter scan; D2 EXPANDED N=42 real-fixture regression; R2-A N=65 verbatim regression)

### Sec 3.3 NEW smoke artifact (exports/research/g2-w-bottom-ruleset-backtest-20260527T213434Z/; 5 files)

- `manifest.json` -- g2_version 1.0; substrates_summary + L2 LOCK assertions + cache_dir
- `scorecard.csv` -- 18 rows (9 rulesets x 2 substrates); 16 columns
- `per_trade_detail.csv` -- 963 rows; substrate_name + 26 Trade dataclass fields
- `summary.md` -- per-substrate scorecard tables + cross-substrate observations
- `narrative_synthesis.md` -- per-(ruleset, substrate) descriptive interpretation

### Sec 3.4 MODIFIED files

- `docs/g2-w-bottom-ruleset-backtest-dispatch-brief.md` -- appended Brief Amendments 1-4 section (banked during Codex MCP pre-smoke chain R1-R4)
- `.gitignore` -- added g2-w-bottom-ruleset-backtest-* exception block

### Sec 3.5 NEW findings + return report

- `docs/g2-w-bottom-ruleset-backtest-findings-20260527.md`
- `docs/g2-w-bottom-ruleset-backtest-return-report.md` (this file)

---

## Sec 4 Codex MCP chain summary (2 chains; both CONVERGED)

### Sec 4.1 Chain #1 (pre-smoke; R1-R5)

5-round chain; CONVERGED at R5 NO_NEW_CRITICAL_MAJOR. Detailed per-round dispositions in `docs/g2-w-bottom-ruleset-backtest-findings-20260527.md` Sec 8.

Cumulative: 3 CRITICAL + 13 MAJOR + 12 MINOR. ALL CRITICAL + MAJOR resolved or accepted-with-rationale. 4 Brief Amendments banked.

**Codex Chain #1 caught REAL defects against actual production code:**
- R1.C1: target formula entry-anchored vs pattern-anchored (brief Sec 2.1 line 156 LOCK violation); fixed across all 3 rulesets
- R1.C2: entry/exit price model harness-parity vs brief-literal (brief Sec 2.1-2.3 LOCK violation); fixed via entry-at-trigger-close + DeferredExit-at-next-bar-open
- R1.M2: D2 EXPANDED N=71 vs actual N=42 substrate drift (gotcha #34 trigger; Brief Amendment 1 banked)
- R2.M2: DeferredExit exit_date/days_held inconsistency (Expansion #13 cumulative regression cascade)
- R3.M1: DeferredExit at data tail marked 'closed' contaminates performance metrics (status semantic correction)
- R3.M2: peak_R can be underreported on next-bar-open gap-up exits (below-zero drawdown_to_exit_R prevention)
- R4.MAJOR: Brief Amendment 1 not propagated to locked brief doc (gotcha #34 sub-refinement direct evidence)

### Sec 4.2 Chain #2 (post-smoke; R6-R7)

2-round chain; CONVERGED at R7 NO_NEW_CRITICAL_MAJOR. Per operator's 2-chain instruction (added after Slice 5a; an additional Codex review point AFTER implementation completion but BEFORE smoke artifact generation, then a separate chain post-smoke for narrative discipline + smoke-output coherence).

Cumulative: 0 CRITICAL + 3 MAJOR + 5 MINOR. ALL MAJOR resolved.

**Codex Chain #2 caught REAL narrative-discipline defects in findings + return report:**
- R6.M1: gotcha #33 banned-verdict-term LOCK violations in findings doc CURRENT-RUN narrative (lowercase 'negative expectancy' / 'positive expectancy' / 'NEGATIVE baseline' as G2-verdict labels; not just historical-context citation); swept + replaced with metric-only descriptors
- R6.M2: gotcha #35 prior-arc-anchor metric-definition incomplete (D2 '+1.220R' had no formula; D_filt loose definition; claimed R2-A '22.5%' citation not actually present in claimed Sec 1+Sec 3); added formula parentheticals + clarified Sec 3 explicit citation
- R6.M3: cross-doc SHA citation incomplete (findings + return report mentioned 'SHA-locked' but didn't cite actual SHAs); added explicit SHA + N + window-days header blocks to both docs

### Sec 4.3 Cumulative across both chains

3 CRITICAL + 16 MAJOR + 17 MINOR. ALL CRITICAL + MAJOR resolved or accepted-with-rationale. 4 Brief Amendments banked in the locked brief doc itself. 2 NEW sub-refinement candidates banked (per Sec 8 below).

**Codex DID NOT catch (operator might still discover at post-merge review):**
- Substrate-window short (21-31d) extrapolation noise in estimated_dollar_per_period -- noted in findings doc Sec 5.1; banked as caveat in V2 candidate #8
- D2 Amendment 5 substrate-freshness sensitivity as a substantive methodology finding -- the IMMEDIATE finding was surfaced by Codex R1.M2 (D2 N=71 vs N=42 drift); the broader methodology lesson (any tight-window substrate verdict may not REPLICATE under regenerate-cohort refresh) is captured in findings doc Sec 4.2 + return report Sec 6 V2 candidates #1

**2 NEW sub-refinement candidates banked from cumulative chain (Sec 8 below):**
- Expansion #2 sub-refinement: ruleset-formula reference-frame discipline
- Gotcha #34 sub-refinement: Brief Amendment immediate-propagation discipline

---

## Sec 5 Cumulative discipline preservation

### Sec 5.1 35 CLAUDE.md gotchas BINDING

| Gotcha | Preservation evidence |
|---|---|
| #1 (test-count drift) | findings doc Sec 8 cites RUNTIME test counts (113 + 1 skip), NOT brief's "~60-100" estimate |
| #26 (OHLCV archive temporal mutation) | Sec 5.5 of findings doc characterizes as L6-style limitation |
| #28+#29 (OHLCV cache discipline) | N/A; G2 is rule-based, not template-matching |
| #31 (narrative artifact path/fact lag) | post-fix-bundle sweep verified at each Codex round; this return report cites latest smoke artifact path |
| #32 (ASCII discipline scope clarity) | declared scope = ALL NEW G2 Python source + tests + emitted artifacts; test_ascii_discipline_g2_python_files_encode_clean parametrized over the full module set |
| #33 (cohort-validity-vs-verdict-criteria) | banned verdict terms NOT EMITTED across scorecard.csv + summary.md + narrative_synthesis.md; this findings doc + return report use DESCRIPTIVE language only |
| #34 (brief-prescription cross-table verification) | Brief Amendment 1 banked (D2 N=42 vs N=71); SHA-locked fixture + brief-locked filter is authoritative |
| #35 (prior-arc-anchor citation) | FIRST CANONICAL APPLICATION shipped; all prior-arc anchors in findings doc cited with metric definitions (D2 Amendment 5 "+1.220R mean R closed (5 of 5 winners)"; R2-A "22.5% win-rate"; V2-mechanic D_filt definitions) |

### Sec 5.2 Architectural LOCKs

- **Sibling-module strategy LOCKED.** A-F + R2-A + D2 + R2-D + V2-mechanic harnesses byte-stable through G2 dispatch. test_existing_harness_byte_stable_through_g2_dispatch verifies all 5 existing files via SHA256 (Codex R1 MAJOR #3 closure).
- **Substrate REUSE VERBATIM.** R2-A cohort.json (N=65) consumed verbatim; D2 cohort.json (N=172) filtered to N=42 via brief-locked spec. Both fixtures SHA byte-stable.
- **Cohort-validity LOCKED at canonical filter.** No substrate substitution; D2 EXPANDED is the brief-locked spec; brief's stated N=71 was stale; actual N=42 surfaces in scorecard + manifest.
- **9-metric scorecard IS the headline.** No single categorical verdict emitted. Operator-paired interpretation at orchestrator layer per gotcha #33 third canonical application.
- **$-amount basis $75/R per brief Sec 11 Q4.** R_DOLLAR_SIZE_AT_7500_FLOOR LOCKED at 75.0; LOCK preserved via test (test_estimated_dollar_per_period_derivation_at_75_per_R).

### Sec 5.3 ZERO violations

- ZERO production swing/ writes (entire diff is research/ + tests/ + docs/ + .gitignore + exports/)
- ZERO new Schwab API calls (L2 LOCK preserved; manifest assertion `schwab_api_calls: 0`)
- ZERO yfinance fetches at backtest time (manifest assertion `yfinance_fetches_at_backtest_time: 0`)
- ZERO V1 persisted state modifications (no DB writes; no schema migrations; Schema v21 UNCHANGED)
- ZERO Co-Authored-By footer trailers (verified via `git log applied-research-g2-w-bottom-ruleset-backtest --format='%h %s' | grep -i 'co-authored\|noreply@anthropic' || echo CLEAN`)
- ZERO use of `--no-verify` on commits
- ZERO verdict terminology in scorecard or narrative output (gotcha #33 BINDING)

---

## Sec 6 V1 simplifications + V2 candidates banked (gotcha V1-simplification-discipline)

| # | V1 simplification | V2 dependency |
|---|---|---|
| 1 | Substrate sizes thin (R2-A N=65; D2 EXPANDED N=42) | V2 dispatch to grow N via larger recency window OR re-extract D2 Amendment 5 N=71 snapshot |
| 2 | NO time-stop in G_bulkowski (Bulkowski does not specify in canon) | V2 explore Bulkowski-cited "60-day W invalidation" extension |
| 3 | Throwback handling for I is engine-default single-entry (no delay-for-throwback variant) | V2 explore wait-for-throwback-then-enter alternative |
| 4 | Volume baseline multipliers (1.3x/1.4x/1.5x) hard-coded from literature canon | V2 parameter-sweep 1.2-2.0x range per ruleset |
| 5 | OHLCV reads use AT-G2-DISPATCH-TIME cache (subject to gotcha #26 temporal mutation) | V2 pre-fetch substrate OHLCV per verdict's anchor_asof_date for data-as-of-pattern-extraction-time evaluation |
| 6 | D1 hand-curated +67 substrate NOT WIRED (--include-d1-cohort raises NotImplementedError) | V2 wire D1 substrate via separate fixture + harness branch |
| 7 | Codex chain #1 surfaced "Brief Amendment propagation discipline" as new expansion candidate | V2 dispatch-brief authoring protocol could pre-empt by IMMEDIATE brief-doc amendment at Codex R1 surface |
| 8 | substrate_window_days 21-31 short; estimated_$/period noisy | V2 longer-window substrate or operator-narrative caveat |
| 9 | gotcha #33 banned-term scan covers summary.md but NOT scorecard.csv (latter is purely numeric) | V2 may extend banned-term scan to CSV cell content if ever populated with descriptive labels |

---

## Sec 7 Sec 11 operator-paired decision LOCK record

Per dispatch brief Sec 11:

| Q | Decision | Implementation |
|---|---|---|
| Q1 (Ruleset selection) | Default G/H/I (Bulkowski + O'Neil + Edwards-Magee) | LOCKED at dispatch; no operator override; implemented as specified |
| Q2 (Substrate inclusion) | Default R2-A + D2 EXPANDED; D1 deferred | LOCKED at dispatch; --include-d1-cohort raises NotImplementedError |
| Q3 (Codex MCP) | YES | LOCKED; pre-smoke chain ran 5 rounds CONVERGED; post-smoke chain runs in Slice 7 |
| Q4 ($-amount basis) | $7500 floor + 1% risk = $75/R | LOCKED via R_DOLLAR_SIZE_AT_7500_FLOOR constant; regression test |

Operator-paired decisions LOCKED through dispatch; ZERO deviations from Q1-Q4. Codex MCP chain surfaced 4 Brief Amendments to the brief BODY (Q1-Q4 unchanged); banked in-place in the brief doc.

---

## Sec 8 44th cumulative C.C lesson #6 validation NOTABLE

Per cumulative discipline: 44th validation slot reserved for G2 dispatch.

Pre-Codex review applied ALL 19 cumulative expansion candidates per dispatch brief Sec 6(h) + Sec 7. Codex still surfaced 3 CRITICAL + 13 MAJOR. **The expansions caught a substantial portion of defect classes BUT not all:**

Caught by expansion #2 family (signature / spec-source-of-truth / cascade verification): R1.M1 (1.3x boundary), R1.M3 (A-F SHA), R3.MINOR #1 (stale docstrings), R3.MINOR #2 (CLI residual N=71).

Caught by expansion #4 family (SQL skeleton verification): N/A (no SQL in G2).

Caught by expansion #11 + #15 (taxonomy / metadata): R3.MINOR #3 (GhiRuleset Protocol).

NOT pre-empted by existing expansions (genuinely novel defect classes for V2 banking):
- **R1.C1 (target formula entry vs pattern-anchored):** the brief Sec 2.1 LOCK was explicit; pre-Codex review SHOULD have caught via expansion #2 (brief-vs-actual cross-check) but the implementer pattern-matched against existing RulesetE convention. **NEW EXPANSION CANDIDATE #20 banked: ruleset-formula pattern-anchored-vs-entry-anchored discipline -- when adapting existing canonical formulas, verify the BRIEF's reference frame (operator-relative vs pattern-relative) matches the implementation's reference frame.**
- **R1.C2 (entry/exit price brief-literal vs harness-parity):** the implementer chose harness-parity as the "safer" reading; brief explicitly LOCKed brief-literal. **EXPANSION #2 refinement: when a brief LOCKs a methodology that diverges from existing-harness convention, the implementation MUST honor the brief explicitly + DOCUMENT the methodology divergence rather than silently aligning with existing convention.**
- **R2.M2 (DeferredExit exit_date/days_held cascade):** Codex caught the second-order regression after the C2 fix. **EXPANSION #13 (cumulative regression cascade) DIRECT EVIDENCE: when introducing a new action type, the engine's ENTIRE Trade-emission path must be re-audited for consistency across the new branch.**
- **R3.M1 (DeferredExit status='closed' at data tail contaminates metrics):** the third-order regression after the M2 fix. **EXPANSION #13 reinforcement: post-fix audit must enumerate semantic invariants (e.g., status field's relationship to exit-execution-feasibility); each new action type carries an exit-feasibility-at-data-tail discipline.**
- **R4.MAJOR (Brief Amendments not propagated to locked brief):** the implementer banked amendments in commit messages + docstrings + tests but NOT in the brief doc itself. **NEW EXPANSION CANDIDATE #21 banked: when Codex surfaces a brief-amendment-grade finding, the AMENDMENT must propagate to the brief doc itself in the SAME fix commit -- not as a separate doc-update follow-up.**

**44th validation outcome:** NOTABLE. The 19 cumulative expansions caught a substantial portion of surfaced defects (qualitative; not a precise measured ratio); the unfilled gap was second/third-order regression cascades + brief-vs-implementation methodology divergences. **2 NEW expansion sub-refinement candidates banked** (NOT full new expansion numbers per Codex R6 MINOR #2 -- both are sub-refinements of existing #2 / #34):
- **Expansion #2 sub-refinement candidate (G2 banking):** ruleset-formula reference-frame discipline -- when adapting existing canonical formulas, verify the BRIEF's reference frame (operator-relative vs pattern-relative) matches the implementation's reference frame. Pattern-matching against existing-harness conventions can silently corrupt brief-LOCKed methodology.
- **Gotcha #34 sub-refinement candidate (G2 banking):** Brief Amendment immediate-propagation discipline -- when Codex surfaces a brief-amendment-grade finding, the AMENDMENT must propagate to the brief doc itself in the SAME fix commit, not as a separate doc-update follow-up.

---

## Sec 9 Forward-binding artifacts + locks for any subsequent dispatch

For future dispatches that reference G2 or extend it:
- **Substrate authority**: R2-A N=65 + D2 EXPANDED N=42 are canonical at G2 dispatch baseline. Subsequent dispatches MUST cite both SHA + N + window-days (gotcha #35 prior-arc-anchor discipline). Brief Amendment 1 (N=42 not N=71) is locked-in.
- **Ruleset authority**: G_bulkowski / H_oneil / I_edwards_magee canonical specs are LOCKED at the implementations + Brief Amendments 2-4. Subsequent dispatches that extend or modify these must amend in-place + Codex-validate.
- **9-metric scorecard authority**: ScorecardRow dataclass (16 fields) is the V1 LOCK. open_at_tail_count + open_at_tail_rate both surfaced (Codex R2 M6 closure). Subsequent dispatches that extend the scorecard must extend the dataclass + tests in-place.
- **DeferredExit + GhiRuleset architecture**: NEW action type + Protocol added for G2; future G2-style harnesses with custom execution semantics may import + extend these.

---

*End of G2 W-bottom-ruleset backtest return report. SHIPPED end-to-end through Slice 8 (all slices complete; both Codex MCP chains CONVERGED at NO_NEW_CRITICAL_MAJOR). Joint hypothesis NOT supported at tested substrate scale; substantive diagnostic substance surfaced via 9-metric scorecard; ZERO production swing/ writes; ZERO new Schwab API calls; cumulative discipline preserved across 35 CLAUDE.md gotchas + 19 pre-Codex expansion candidates; 2 NEW sub-refinement candidates banked for future dispatch authoring (Expansion #2 sub-refinement + Gotcha #34 sub-refinement). Dispatch deliverable READY for operator-paired post-merge review + next-arc disposition decision.*
