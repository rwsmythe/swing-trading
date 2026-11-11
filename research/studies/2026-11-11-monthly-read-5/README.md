# Monthly read #5 — the November read, the stage-1 widening read, and the stage-2 recommendation

**Author:** RD. **Date:** 2026-11-11 (the November monthly read, owed for the first trading week; paid on the operator's word in session, one week late). **Standard:** watch-standard v2.5.
**Cited artifact:** `shadow-expectancy-20261111T033347Z` (run 211, data as of 2026-11-10), copied to `artifacts/` per v2.1 (cite = commit).
**Extends:** [`2026-10-18-monthly-read-4/`](../2026-10-18-monthly-read-4/). **Scripts:** `read5.py`, `stage1.py` in this directory (committed this time; read #4's were not).
**Every number below was read fresh on 2026-11-11 from the live DB `mode=ro` (schema v41) and the cited artifact.**

**Bottom line.** Nothing is decided by this read. T4 stays banked negative and its trajectory is softer, not reversed. Stage 1 of the screen widening cost nothing that binds and bought nothing that fired: zero A+ fires, and both hypothesis fires in the window came from names the OLD screen would have carried. One instrument finding matters for stage 2: the 52-week-high filter is NOT binding at 25%. Stage 2 is recommended, with that filter settled first.

---

## 1. The monthly read (watch-standard §3.1)

**1. Drumbeat.** 17 of 17 NYSE sessions 2026-10-19..11-10 have an evaluation run and a shadow artifact. No gap. The 11-06 nightly did not fire on schedule (operator travelling, box off; operator-stated 2026-11-10) and ran as a Saturday 05:41 HST catch-up (run 209, data as of 11-06). 10-24 is the one cause-unconfirmed miss from before this window. T1 untripped.

**2. Funnel (newest).** 8,770 detections → 1,754 unique signals → **0 unattributed** (all four unattributed classes zero). +219 signals since read #4 (1,535).

**3. Pricing.** Broad-watch trigger 1,146 / 1,590. Priced closed 1,061 signals / 190 names; triggered 1,146 / 199 names. Mature (age ≥ 30 sessions) closed 964 / 170 names. Scenarios, realistic: closed_only −0.301 (1,061) · mtm −0.152 (1,146) · forced_exit −0.152 · stop_level_adverse −0.254. Favorable arm −0.189 / −0.049 / −0.049 / −0.151. Every scenario on both arms negative.

**4. Log maturity.** Detections 2026-06-05..2026-11-11, 307 tickers; 443,679 forward observations through 11-10. T9, score > 0, distinct names: HTF 198 · VCP 105 · DBW 55 · CWH 40 · FB 33 (read #4: 165 / 94 / 35 / 35 / 29).

**5. Live record.** One new trade: 29 SG, entered 2026-11-06, 11 sh at 11.95, stop 8.98, `hypothesis_test_by_design`. **T7 was raised by the operator's glance on 11-10 and ruled the same day: a legitimate H2 fire** (eval 193, data as of 11-04, SG failing only `proximity_20ma`; the real matcher returns the H2 label on that row; the order was placed on that fire and held through a one-night lapse; fill at the fire's pivot). The row's label is wrong (`Broad-watch baseline …`): the entry-form prefill stamps the latest run at lock (gotcha #30 on the label). Operator concurred 11-10 that the label becomes the fire's H2 label by a recorded correction; mechanism is CHARC's; **not yet applied**. Until then SG counts in no cohort. The shadow engine independently attributes SG's 11-04-data detection to the H2 arm (+1.44R mark, open), which corroborates the ruling. SG unrealized: close 13.24 on 11-10, about +0.43R. No closed trades since read #4. Zero A+ candidate rows since id 13591: **zero A+ fires since 09-02; the admitting-gate witness and the first risk-flagged A+ witness both stay open.** Intent contract HELD.

**6. Hypothesis progress (reader, `swing hypothesis list`).** H1 4/20 · H2 4/10 (5 once SG is corrected and closes) · H3 10/5 met · H4 0/10 · H5 3/30 live-standard, DECIDED on the shadow substrate. No decision criterion is within reach.

**7. Posture.** UNCHANGED: stop-engineering + market time. Stage 2 below is a config edit under the already-approved widening rider, not new engineering.

### T4 trajectory (banked at read #4; reported, NOT re-decided)

| cohort (detection month; min age in sessions to 11-10) | triggered | closure | closed n / names | closed mean R [95% CI] | non-ETF (n) | mtm (n) |
|---|---|---|---|---|---|---|
| June (93) | 193 | 97.9% | 189 / 58 | +0.1181 [−0.254, +0.491] | +0.3186 (160) | +0.1651 (193) |
| July (71) | 345 | 94.8% | 327 / 80 | −0.5056 [−0.623, −0.389] | −0.4665 (297) | −0.4038 (345) |
| August (50) | 269 | 93.3% | 251 / 72 | −0.4170 [−0.561, −0.273] | −0.4204 (247) | −0.3034 (269) |
| September (29) | 215 | 94.4% | 203 / 43 | −0.1777 [−0.434, +0.079] | −0.2609 (193) | −0.0865 (215) |
| October (7; immature) | 86 | 82.6% | 71 / 25 | −0.1995 [−0.557, +0.158] | — | +0.2563 (86) |
| November (1; immature) | 38 | 52.6% | 20 / 12 | −1.0530 (resolution speed) | — | +0.2872 (38) |

Pooled, age ≥ 30: **closed_only −0.2874 [−0.394, −0.181], n = 964**; **mtm −0.1976 [−0.303, −0.092], n = 1,015**; non-ETF closed −0.2654 [−0.378, −0.153] (893). Win rate 237/964 = 24.6%, Wilson LB 22.0%. Exit mix: initial_stop 608 · breakeven_stop 245 · ma_close_below 111. ETF slice at maturity: 71 closed / 12 names, −0.5637 [−0.868, −0.260] (December T10 item, unchanged).

Read: the pooled primary moved from −0.3618 to −0.2874 because September matured near −0.18 with a CI spanning zero, while July and August softened slightly as their last open rows closed. Both primaries still exclude zero by more than their half-width (0.106 vs 0.287; 0.105 vs 0.198). **The bank stands.** Regime dependence across detection months is now four cohorts wide (June +0.12, July −0.51, August −0.42, September −0.18): the watch complement loses, and how much depends on the month. Bracket table (closed-only, regime-confounded, not the instrument): ≥0 −0.301 (1,061) · ≥30 −0.287 (964) · ≥50 −0.323 (767) · ≥70 −0.273 (526) · ≥90 −0.018 (239) · ≥100 +0.315 (100, June).

Other arms. Shadow A+ 7 closed, −0.590 (1/7), unchanged since read #4, with the standing caveat (entry-bar-low stop geometry, not the live mandate). Shadow H2 arm 16 triggered of 19, closed 15 at −0.122 (6/15 wins), mtm −0.024 (16).

### Era keys (v2.4 §4, v2.5)

| era (by `run_id` of the detection) | triggered / names | closed | mtm |
|---|---|---|---|
| pre-D84 (run < 200) | 1,096 / 189 | −0.2811 (1,032) | −0.1703 (1,096) |
| D84, pre-widening detect (200..202; 201 and 202 are the hole) | 7 / 7 | −0.531 (4) | +0.961 (7) |
| widened (run ≥ 203) | 43 / 16 | −1.071 (25) | +0.121 (43) |

The widened era is nine sessions old. Its closed mean is initial stops resolving first, exactly the v2.2 resolution-speed signature. **Nothing about the widened population's expectancy is readable before roughly mid-December.**

### Data-quality watches, both sides of the boundary (owed by v2.4)

- `invalid_ohlc`: **71, flat on every manifest 2026-09-24..11-11**, both sides of D84 and of the widening. 4.05% of 1,754. Plateaued; the widening added none.
- `degenerate_risk`: 30 flat 10-18..10-30 → 33 (10-31) → 35 (11-06). **All five additions land after the first widened detections (run 203).** Mechanism unchanged (the 19-D risk-unit floor, rps < 0.15 × ADR); the widened pool carries tight-stop names at a slightly higher rate. 2.0% of signals. Watch, not a defect.
- `insufficient_forward_depth` 2..26 and `missing_observations` 7..32: noise band, self-healing, no step.
- Risk flags (D84): **122 risk non-pass rows on evals 188..197, zero before** (evals 186, 187: 0). 108 on `skip`, 14 on `watch`, 0 on `aplus`. Every one is in a class the price cap used to exclude (§2). The boundary that was "quiet by observation" in v2.4 is now populated, on watch and skip only. H4 still has had no eligible card.
- Research health: GREEN on every nightly artifact read in the window.

---

## 2. Stage 1 of the screen widening: what it cost and what it bought

Window: evals 188..197 (data as of 10-28..11-10, ten nightlies) against evals 176..187.

**Cost. Nothing binds.**

| | pre (runs 197..201, post-D90) | widened (runs 202..211) | trigger |
|---|---|---|---|
| screen rows per fetch | 27..45 | 135 → 65..103 as the tape contracted | — |
| evaluate wall | 79..94 s | 71..151 s (325 s on the first night only) | — |
| detect wall | 21..25 s (201 dead) | 21..66 s, about 2.5 s per watch name | — |
| observe wall | 42..49 s | 51..83 s (131 s on the first night only) | 1,800 s |
| whole run | 171..206 s | 205..365 s (543 s on the first night only) | — |

No monitor rate moved (above). The uncapped ruling of 10-29 holds on measured cost: outside the first night the largest observe wall is 4.6% of the trigger (7.3% on the first night).

**Yield. Split by which filter admitted the row** (class from the row's own close and the evaluator's own 52-week-high distance):

| class | rows | distinct tickers | watch rows | watch rate | distinct watch tickers | one-miss rows | risk-flagged |
|---|---|---|---|---|---|---|---|
| old screen (≤ $100, ≤ 10% off high) | 444 | 96 | 117 | 26.4% | 38 | 21 | 0 |
| price cap lifted (> $100, ≤ 10% off) | 116 | 36 | 31 | 26.7% | 18 | 2 | 47 |
| > 10% off high (≤ $100) | 329 | 102 | 22 | 6.7% | 12 | 4 | 7 |
| both | 91 | 36 | 7 | 7.7% | 5 | 3 | 68 |

Pre-widening baseline (evals 176..187): 446 rows, watch rate 27.4%, 34 distinct watch tickers.

1. **The price-cap lift admits names that behave exactly like the old screen** (26.7% vs 26.4% watch rate). It is the half that worked as designed. 41% of its rows carry the risk flag, which is D84 doing its job: these are the "$600 stock" names of the operator's declaration, now visible instead of silently skipped.
2. **The near-high half is mostly dead weight.** 6.7% watch rate. These rows die at the trend template (TT2 66%, TT3 64%, TT7 59%, TT4 47%), not at the VCP layer. 420 of 980 widened-window rows are in the two off-high classes and produce 29 watch rows.
3. **Zero A+ fires. Zero H4 cards. Two H2 fires in 22 evaluations (GTLB eval 187, SG eval 193), both old-screen names.** Stage 1 produced no program fire the old screen would not have produced.
4. **The binding failures are the same in every class: `tightness` (87..99% of rows) and `proximity_20ma` (50..66%).** All 30 one-miss rows but one miss on tightness. The screen is not what stands between the pool and A+; extension and the tape are. This matches the rider's stated expectation ("names 10-25% off their highs mostly die at tightness and proximity … the regime is not fixed by any screen").

**Instrument finding: the 52-week-high filter is not binding at 25%.** The evaluator's own TT7 distance on the widened rows: ≤ 10%: 560 · 10..25%: 202 · 25..30%: 32 · 30..40%: 20 · **> 40%: 166** (the last bucket includes recent listings where TT7 is `na` for lack of 200 bars). 219 of 980 rows (22%) do not pass TT7, against 8 of 446 (1.8%) before the widening, where the 8 are one-day drift. Spot-checked against the archive: WING last 169.58 vs a 252-bar high of 284.66 (2026-01-12); EPAM 164.14 vs 221.40; ZS 194.92 vs 331.29; DOCS 33.18 vs 63.99. Those highs are real prices, so the archive is right and the screen let through names 40% below their highs. **Most likely `ta_highlow52w_b0to25h` is not a value Finviz honors and the filter is being ignored**, so stage 1 as applied was "cap lifted + no near-high filter", not "25%". I have not called Finviz to confirm; the check is one look at the screen in the Finviz UI (does the 52-Week High/Low dropdown show a value or "Any" for that URL).
Consequences: (a) no measurement damage, because TT7 is not an allowed miss and every such row is `skip`; (b) the cost is evaluate time on about a fifth of the rows plus the ETF count (108 ETF rows in the window against 22 before, 4 watch rows each side); (c) the v2.5 boundary note's query text is still literally true, and gains an addendum saying the token does not bind; (d) the 10-19 count "cap + 25% = 109" was a count of the unfiltered screen.

---

## 3. Stage 2 recommendation

**Recommendation: GO on stage 2 (`ta_perf_13w30o` → `ta_perf_13w10o`), with the near-high filter settled in the same edit.**

Why go:
- **Cost is not a constraint** (figure CORRECTED in section 6: stage 2 is 2.1x to 3.7x rows, not +11%; the conclusion survives, the number did not). The observe wall has more than 20x headroom.
- **It is the only screen lever aimed at the measured binding constraint.** A 13-week performance floor of 30% selects names that are still running, and the pool shows it: tightness fails on roughly nine rows in ten and proximity on more than half. A name that ran and then spent a quarter basing has LOW 13-week performance by construction; the 30% floor screens it out exactly when it becomes interesting. The evaluator's `prior_trend` (≥ 25%, its own longer window) still demands the prior run, and TT1..TT7 still demand the structure, so the gate is unchanged. This is a hypothesis about where A+ candidates are hiding, not a finding; the two-week read after the edit tests it by the one-miss and A+ counts, not by expectancy.
- **Nothing in stage 1 argues for stopping.** It did no harm and its failure to produce fires is explained by the regime and by filter choice, not by the population being wrong.

Conditions, all small:
1. **Settle the 52-week-high filter first, in the same edit.** Either replace `b0to25h` with a token Finviz honors (the operator verifies in the UI), or leave it deliberately unfiltered and say so. My preference is a real filter no tighter than the gate: TT7 does the check either way, and a binding filter removes about a fifth of the evaluate work and most of the leveraged-ETF rows. If Finviz offers no 25% value, 20% is acceptable and costs nothing measurable (rows 20..25% off: a small slice of a class with a 6.7% watch rate).
2. **One edit night, one boundary.** Both changes land together; I write the watch-standard boundary note (v2.6) on the first run that evaluates the new CSV, naming the query text, the first call id and the first evaluation run. `select_csv` consumes the previous night's CSV, so the first stage-2 evaluation is the night AFTER the edit.
3. **The cap stays unset.** Same ruling, same reason; it is re-opened only by a measured wall.
4. **The read after it is pre-stated:** two weeks; one-miss rows per night and their miss criterion; A+ fires; H2/H4 fires and whether the name is stage-2-admitted (13-week performance between 10% and 30% at fire); the same cost series. Expectancy of the widened population is NOT readable in that window and I will not quote it.

What I am not recommending: the ETF exclusion (December T10, unchanged), the volume floor (stays 1M, the one filter the gate does not re-check), any change to the gate.

**Blunt version.** Stage 1 was harmless and so far useless: ten nights, three times the rows, no A+ and no fire the old screen would have missed, in a tape that has produced no A+ since 09-02. Half of it (the price cap) was right; the other half was a filter that silently did not apply. Stage 2 is cheap and better aimed, and I expect it to add watch names and a few one-miss names rather than A+ fires while this regime lasts. The honest reason to do it is that it costs nothing and removes a filter working against the setup the framework wants. H1 is still four trades.

---

## 4. §3.2 log entry (appended to charter §7)

See `docs/research-director-context.md`, entry `2026-11-11 — monthly watch read #5`.

## 5. Methods

Ages: NYSE sessions via `exchange_calendars` XNYS, detection_date → 2026-11-10. Closed = `exit_reason` set, not `horizon_mtm`, `open_at_horizon=False`; mtm = all triggered rows. CIs normal approximation, mean ± 1.96·SD/√n; Wilson z = 1.96. ETF set = `candidates.industry='Exchange Traded Fund'` (75 tickers). Era key = the detection's `run_id` in `results.csv`. Stage-1 classes: `candidates.close > 100` for the cap; the absolute value parsed from the `TT7_within_52w_high_25pct` criterion row for the off-high distance (an `na` TT7 parses as far-off and is called out where it matters). One-miss = exactly one non-pass criterion excluding `risk_feasibility`. Hypothesis fires = `match_candidate_to_hypotheses` on the persisted candidates of each evaluation, narrow phase only. Walls from `pipeline_step_timings`. The eval-178/179 rows share run 193 (a same-day rerun) and are in the pre baseline as persisted. Not done: no Finviz call was made to confirm the filter token; no live R was computed (no closed trade since read #4).

---

## 6. ADDENDUM 2026-11-11 (same day): the token is CONFIRMED ignored, and a CORRECTION to section 3's cost figure

On the operator's go, eighteen read-only calls to the Finviz export endpoint at about 07:20 HST 2026-11-11 (direct, outside the CLI: no `finviz_api_calls` row, no inbox CSV, tonight's fetch untouched). Row counts, with the four unchanged filters held (`sh_avgvol_o1000`, `sh_price_o5`, `ta_sma20_sa50`, `ta_sma50_pa`):

| 52-week-high token | with `ta_perf_13w30o` | with `ta_perf_13w10o` |
|---|---|---|
| none | 74 | 276 |
| `ta_highlow52w_b0to25h` (the live token) | **74** | — |
| `ta_highlow52w_b0to10h` | 30 | 153 |
| `b0to15h`, `b0to20h`, `b0to30h`, `b25h` | 74, 74, 74, 74 | 277, 276 (15, 20) |
| `b20h` (20% or more BELOW the high) | 23 | — |
| `b30h` (30% or more below) | 18 | — |
| `0to25-bhx` (custom-range form) | 45 | — |
| `-25to0-bhx` | 8 | — |

1. **CONFIRMED: `ta_highlow52w_b0to25h` is silently ignored.** It returns the unfiltered count. So do `b0to15h`, `b0to20h`, `b0to30h` and `b25h`. Finviz answers 200 with a full CSV for an unknown token. Of the "within N% of the high" presets only `b0to10h` (and `b0to5h`: 18) binds.
2. **There is no clean 25% token.** By subtraction, within 20% = 74 - 23 = 51 and within 30% = 74 - 18 = 56, so within 25% is about 53. The custom-range form `0to25-bhx` returns 45 and `-25to0-bhx` returns 8; 45 + 8 = 53, which reads as the custom range EXCLUDING names sitting exactly at the high. That is an inference from counts, not a documented semantic, and a filter that drops the names at new highs is the wrong filter. Not recommended.
3. **CORRECTION to section 3.** I wrote that stage 2 adds "about +11% rows (109 -> 121)". That was a misread of the 10-19 counts: 121 was perf-10% on the OLD screen; the same note put all three changes at about 299. Measured today: stage 2 with no near-high filter is **276 rows against 74, 3.7x**; with `b0to10h` it is **153 rows, 2.1x**. The "more than 20x headroom" statement holds for the observe wall only; evaluate scales with rows (about 1.2 to 1.5 s per row, so roughly 5.5 to 7 minutes at 276) and is not trigger-bound.
4. **The choice this puts to the operator** (section 3's condition 1, now concrete):
   - **A. No near-high filter: 276 rows.** The screen is never stricter than the gate, which is the rider's ruled intent; TT7 does the whole check. Cost: a run of roughly 8 to 10 minutes and a larger watch pool. `b0to10h` is the known-binding fallback if a wall ever approaches its trigger.
   - **B. `ta_highlow52w_b0to10h`: 153 rows.** Restores the pre-widening near-high value. Drops the class that produced a 6.7% watch rate and no fire in stage 1.
   - **RD recommendation: A.** The stage-1 evidence against the off-high class was gathered UNDER the 30% performance floor, where an off-high name is mostly a broken trend. Under a 10% floor the off-high names include the ones basing 10 to 25% below their highs, which is the depth of an ordinary base; B would remove them at the same moment stage 2 admits them. The cost of A is minutes, not a tripwire.
