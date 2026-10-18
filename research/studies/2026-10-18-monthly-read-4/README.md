# Monthly read #4 — T4 DECISION READ: the broad-watch baseline is NEGATIVE at maturity, and it is BANKED

**Author:** RD. **Date:** 2026-10-18 (the October monthly read, owed for the first trading week of October and paid late under the watch standard's §1 catch-up discipline — the seat's predecessor rolled 09-28 and the operator's declared travel pause ran ~10-03..10-20; read on the operator's word 2026-10-18).
**Cited artifact:** `shadow-expectancy-20261018T234055Z` (run 194, data as of 2026-10-16), copied to `artifacts/` per v2.1 (cite = commit).
**Extends:** [`2026-09-02-monthly-read-3/`](../2026-09-02-monthly-read-3/) and [`2026-08-01-t4-maturity-withdrawal/`](../2026-08-01-t4-maturity-withdrawal/) — same instrument, same method (§6), one more month of age.

> **VERDICT — T4 BANKED, NEGATIVE.** Under the frozen 0026 criterion (realistic arm; closed_only AND
> mtm_at_horizon primaries; N≥30 priced shadow signals) read through the v2.2 maturity gate (cohort age
> ≥30 NYSE sessions; CI width smaller than the distance to zero), the broad-watch baseline's expectancy is
> **closed_only −0.3618 [−0.474, −0.249] (n=766 / 152 names) and mtm_at_horizon −0.2895 [−0.406, −0.173]
> (n=785).** Both primaries are negative, both intervals clear zero by more than their half-width, and the
> result holds with the ETF slice removed (closed −0.3141 [−0.436, −0.193]; mtm −0.2368 [−0.362, −0.112]).
> Per the registry row's own pre-registration: **"negative or zero mean R is a bankable validation of A+
> gate selectivity."** That is what is banked — and only that. It does NOT establish that A+ has positive
> expectancy (H1 is 4/20); it establishes that the mechanical ruleset applied to the watch-pool complement
> — the population the temporal log contains and the operator has historically traded by hand — LOSES.

## 1. The equal-age comparison (the instrument; ages in NYSE sessions to 2026-10-16)

| cohort (detection month) | triggered | closure | mature closed n / names | closed mean R [95% CI] | non-ETF mean (n) | mtm mean (n) |
|---|---|---|---|---|---|---|
| June (min age 76) | 193 | 97.9% | 189 / 58 | **+0.1181** [−0.254, +0.491] | +0.3186 (160) | +0.1651 (193) |
| July (min age 54) | 321 | 99.7% | 320 / 79 | **−0.5354** [−0.653, −0.418] | −0.4984 (290) | −0.5307 (321) |
| August (min age 33) | 244 | 94.3% | 230 / 69 | **−0.5370** [−0.651, −0.423] | −0.5427 (226) | −0.3448 (244) |
| September (immature; only 27 rows past 30) | 185 | 86.5% | 27 / 17 | −0.1713 [−0.642, +0.300] | — | — |
| October (5 rows, nothing mature) | 5 | 60% | 0 | — | — | — |

Read #3's finding stands and is now REPLICATED: two independent cohorts (July, August) past the maturity
gate agree at −0.54 with overlapping CIs, and June — the only positive cohort — was never significant (its
own CI spans zero at 97.9% closure; the fixed-cohort curve read +0.1241 on 09-02 and **+0.1181** today).
**Regime dependence across detection windows is real (June vs July/August differ by ~0.65R), and the bank
is on the POOLED frozen criterion, which the June cohort cannot rescue:** dropping June makes the pooled
number MORE negative, not less.

## 2. The pooled restatement at maturity, against the frozen 0026 primaries (the decision table)

| measure (age ≥30) | n | mean R | 95% CI | vs zero |
|---|---|---|---|---|
| closed_only, pooled (PRIMARY) | 766 | **−0.3618** | [−0.474, −0.249] | negative, CI excludes 0 |
| mtm_at_horizon, pooled (PRIMARY) | 785 | **−0.2895** | [−0.406, −0.173] | negative, CI excludes 0 |
| closed_only, non-ETF | 703 | −0.3141 | [−0.436, −0.193] | negative, CI excludes 0 |
| mtm_at_horizon, non-ETF | 722 | −0.2368 | [−0.362, −0.112] | negative, CI excludes 0 |

Win rate at maturity (closed-only): **181/766 = 23.6%, Wilson LB 20.8%.** All-age artifact scorecard, four
scenarios (realistic): closed_only −0.377 (n=902) · mtm −0.241 (948) · forced_exit −0.241 (948) ·
stop_level_adverse −0.349 (948); favorable-reprice arm −0.269 / −0.138 / −0.138 / −0.247. Every scenario on
both arms is negative. Exit mix at maturity: initial_stop 496 · breakeven_stop 193 · ma_close_below 77 —
the winner-resolution window is fully developed (the `ma_close_below` share has been steady since August).

**v2.2 banking test:** (i) age past the winner-resolution window — YES for June/July/August, which carry
739 of the 766 mature closed rows; (ii) CI half-width (0.112 closed / 0.117 mtm) smaller than the distance
to the boundary (0.362 / 0.290) — YES on both primaries. **BANKED.** The bracket-gradient caveat of read #3
still holds (the pooled ≥N table improves with N because older brackets are increasingly June — a regime
artifact, not maturity); it is reported in §6 and is NOT the decision instrument.

**What the bank licenses, per the registry text:** a validation of A+ gate selectivity — the gate is
excluding a population with negative mechanical expectancy. **What it does not license:** any screen
change (the ETF composition question stays a December-T10 item), any deployment, any statement about A+'s
own expectancy (H1 is 4/20, mean R +0.011 on the four — a diagnostic, not a decision). Cohort-refinement
research is the registry's prescription for a POSITIVE result and is therefore NOT triggered.

## 3. The ETF slice (universe composition; unchanged disposition)

Mature closed ETF signals: **63 / 9 names / mean −0.8935** — 58 died at `initial_stop`, 3 `ma_close_below`,
2 `breakeven_stop`; 5 winners appeared this month (reads #2/#3 had zero). Still unambiguously negative, still
short of the V2.1 promotion gate's 6-month clock. **Re-check at the December T10; not a screen change.**

## 4. The A+ arm and the live-vs-shadow pairs — reported ONLY with the binding caveat (v2.2 OQ-3)

> **CAVEAT (binding, ruled 2026-08-25):** the shadow A+ arm stops at the ENTRY-BAR LOW; the live mandate
> doctrine stops at the FROZEN CANDIDATE STOP. The arm's mean (headline −0.590 closed, n=7, 1/7 wins)
> measures ITS OWN geometry, not the doctrine's.

**The stop-axis pair comparison (owed by the quarterly pass, paid here from existing artifacts + fills):**

| mandate | shadow twin R (entry-bar-low stop) | live realized R (mandate stop) | live exit | reading |
|---|---|---|---|---|
| NVCR 06-18 | −1.000 stop | not taken (pre-latch) | — | — |
| AMN 07-01 | 0.000 breakeven | not taken | — | — |
| FTRE 07-20 | +0.443 breakeven | **−0.092** (trade 19) | stop raised to the framework's own trail candidate | trail-TIMING divergence (both sides mechanical) |
| AMN 08-03 | −0.577 ma_close_below | **−0.996** (trade 20, `unintended_execution`) | stop | decayed-latch spike fill — in NO cohort |
| OII 08-10 | −1.000 stop | **−0.462** (trade 25) | manual go-flat 09-17 | exit by DECISION, not ruleset — excluded from the stop-axis read |
| CADL 08-11 | −1.000 stop | **+0.429** (trade 23: trim +1.23R on 9 sh, stop-hit −0.37R on 9 sh) | stop-hit 09-11 at the raised stop | **SIGN FLIP, now REALIZED** — the only pair where both sides ran their own stop to completion |
| RHI 08-13 | −1.000 stop | **−0.760** journal (−0.72 true; `initial_stop` 34.77 vs the deliberate 34.18 broker stop) | manual go-flat 09-17 | exit by decision; the R-denominator caveat binds |

Four of five shadow A+ twins died at entry-bar-low stops; the live positions stopped at the mandate stop
ZERO times (CADL's 09-11 stop was a RAISED stop after a +1.2R trim). The stop-axis divergence is
systematic and now carries one fully-realized sign flip. **N=5 live, two of them go-flat exits — bank
nothing; this is the §VII.F doctrine read's evidence pile, not a finding.** The trail-from-entry vs
trail-later comparison the quarterly pass asked for is **NOT derivable from the existing artifacts**: the
engine runs ONE trail rule and `per_session.csv` records the exits it produced, not the counterfactual
path; it needs a re-simulation (an engine parameter, a research arc — not commissioned by this read).

## 5. §3.2 log entry (appended to charter §7; duplicated here for the study record)

- Drumbeat: 24 complete runs / 31 NYSE sessions 09-03..10-16 — **7 sessions MISSED (10-05, 10-06, 10-07, 10-08, 10-12, 10-13, 10-15).** T1 fired by the letter (four consecutive) INSIDE the declared pause; cause operator-stated 2026-10-18: the laptop travelled with him and was powered off — a declared-pause miss, NOT a pipeline defect; the scheduler caught up on wake (runs 191/192/194 at off-schedule hours, task result 0). No fix owed. **Consequence: permanent forward-observation holes on 190 broad-watch signals detected 09-01..10-02 (163 already closed); the engine excludes rather than guesses, so the cost is sample size, not bias.** Research-health coverage_gaps read RED from the in-run monitor on 10-11 and 10-18 and GREEN from the probe 20 s later — routed to CHARC as a cry-wolf question (hypothesis: the run's own completion is not yet visible to the step that emits the mail).
- Funnel (newest): 7675 detections → 1535 unique signals → 0 unattributed. Delta since read #3: +1735 detections / +347 signals.
- Pricing: trigger 948/1357 broad-watch; priced closed N=902 signals / 152 unique names at maturity (gate 30 — long crossed); scenarios closed_only 902 / mtm 948 / forced 948 / adverse 948.
- Log maturity: detections 2026-06-05..2026-10-16 (92-session longest window); 267 distinct tickers; 330,648 forward observations (was 168,092).
- Live epoch record: **0 new entries since read #3** (28 PBF, entered 09-01, was labelled after read #3: `by_design` H2 hyp-rec fill under the hyp-rec latch doctrine). Exits: 23 CADL stop-hit 09-11 (+0.429R realized, H1 member); 27 TVTX 09-02 (+0.01R, reason `other`); **the 09-17 deliberate GO-FLAT: 24 RHI −0.76R, 25 OII −0.46R, 26 NRIX −0.28R, 28 PBF +0.21R, all `manual`** (charter §7 2026-09-22 — the PM's call, not a slip; exit-timing on these rows is by decision). Intent contract: HELD. Discipline tags: `none_observed` on all six; exit grade B self-assigned on 24/26/28. Book FLAT since 09-17. **One live question for the operator:** `equity_delta` +$219.57 (ledger minus swing NLV) UNRESOLVED on five consecutive reconciliation runs 09-26..10-03 — the RKLB out-of-framework buy (+3 sh, ~$213–222) is the obvious candidate for an unrecorded OOF cash outlay (the SPCX path-(a) precedent); immaterial-flagged, not a T6.
- Hypothesis progress (reader `hypothesis list`, 2026-10-18; raw label-text count agrees by method): **H1 4/20** (17 VSTS +0.05, 18 AMN +0.02, 23 CADL +0.43, 25 OII −0.46; mean +0.011 — diagnostic only), **H2 4/10** (14, 21, 22, 26 — the fourth is 26 NRIX, confirmed), H3 10/5 closed-target-met, **H4 0/10**, **H5 3/30 live-labelled (19 misfiled, 24 misfiled, 27) — H5's PRIMARY read is §1–2 of this study (shadow-measured per its registry row), and it is DECIDED.** Trade 20 is `unintended_execution` — in no cohort.
- Tripwires since read #3: **T1** ×1 (the pause miss, disposed above); **T4 DECISION READ EXECUTED — BANKED NEGATIVE** (§2); T3 standing nonzero (priced A+ 7; next hand-walk owed at N=10); T5 ×0 (**zero A+ fires since 09-02; the admitting-gate witness stays OPEN** — IMNM link 3/4 and DFTX link 2 are the resting mandates; `candidates.bucket='aplus'` with id>13591: 0); T6/T7 none; T9 — pattern counts (score>0, distinct names): HTF 165, VCP 94, CWH 35, **DBW 35 (was 0 of 1,302 at the quarterly — the detector now fires; W substrate dated from run 176)**, FB 29; gate open by scale on HTF only; predicates 3–5 unmet.
- Data-quality watches: `invalid_ohlc` **71 FLAT** on every manifest 09-24..10-16 (4.6% of 1535; the August climb is over — downgraded from "accelerating" to "plateaued"); **`degenerate_risk` 23 → 29 (10-14) → 30 (10-16), a NEW mover** — the 19-D risk-unit floor (rps < 0.15×ADR) excluding tight-stop signals; mechanism known, incidence to be re-read in November; research-health YELLOW only on the standing excluded-reason breakdown.
- Posture: **UNCHANGED — stop-engineering + market time.** The banked negative originates NO engineering demand and NO screen change. It sharpens the standing "do NOT" line: the watch pool the operator has historically traded by hand has negative mechanical expectancy, replicated across two mature cohorts. The constraint on the program is unchanged: H1's 20 closed `standard` A+ trades, at the A+ fire rate (zero fires in six weeks), with the book flat.

## 6. Methods (every number's source)

Ages: NYSE sessions via `exchange_calendars` XNYS, index distance detection_date → 2026-10-16 (the artifact's newest observation). Closed = `exit_reason` set AND `open_at_horizon=False` in `results.csv`; mtm = all triggered rows (open rows carry mark R). CIs: normal approximation, mean ±1.96·SD/√n. Wilson LB: z=1.96. ETF set: `candidates.industry='Exchange Traded Fund'` (53 tickers today; 52 at read #3). Live DB read `mode=ro`, schema v41 (`SELECT version FROM schema_version`). Live R per trade = Σ(exit price − entry price)×qty ÷ ((entry − `initial_stop`)×entry qty) over `fills` — RHI's denominator caveat as recorded. The pooled age-bracket table (closed-only, regime-confounded, NOT the decision instrument): ≥0 −0.377 (902) · ≥30 −0.362 (766) · ≥50 −0.304 (557) · ≥70 −0.107 (295) · ≥80 +0.259 (131, i.e. June). Fixed-cohort June curve across the 90 surviving artifacts: −1.0 @30.0% (06-13) → −0.714 @26.9% (06-17) → +0.1181 @97.9% (10-02 onward, unchanged since) — the keep-90 prune has now removed the 06-11/06-12 artifacts; the series' start survives only in the committed read-#2 study. Analysis script: the RD scratchpad `read4.py` (method as stated here; not committed — the numbers are reproducible from the committed artifact + this section). No capital-cycle or holding-period figure crosses the correction-38 boundary in this read.
