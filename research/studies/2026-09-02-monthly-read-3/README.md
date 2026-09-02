# Monthly read #3 — the out-of-window replication FAILED: June's positive was the regime, not the edge

**Author:** RD. **Date:** 2026-09-02 (the September monthly read, watch-standard §1 binding cadence; first read under **v2.2** — the maturity gate applies and this read banks NOTHING, by its own rule).
**Cited artifact:** `shadow-expectancy-20260902T035031Z`, copied to `artifacts/` per v2.1 (cite = commit).
**Extends:** [`2026-08-01-t4-maturity-withdrawal/`](../2026-08-01-t4-maturity-withdrawal/) — same instrument, one more month of age.

> **VERDICT: T4 REMAINS UNDETERMINED — but the constraint has reversed direction.** August's unbanked
> mature estimate (+0.2020, ≥30 sessions) has NOT replicated out of window: the July detection cohort,
> now past the same maturity gate, reads **−0.6752 [95% CI −0.81, −0.54]** (n=199, 57 names). The
> pooled mature bracket is **negative on the closed-only primary (CI excludes zero)** and marginally
> indeterminate on the mtm primary. The POSITIVE direction is now the unsupported one. August's refusal
> to bank the +0.20 is vindicated in full — "a single favorable regime reproduces this result entirely"
> was the stated concern, and that is what it was.

## 1. The equal-age comparison (the reason this read exists)

Ages in NYSE sessions (exchange_calendars XNYS), detection date → newest observation 2026-09-01;
closed-only, realistic arm; ETF split via `candidates.industry='Exchange Traded Fund'` (52 tickers,
the read-#2 method).

| cohort (detection month) | closure | closed mean R | 95% CI | n / names | non-ETF mean (n) |
|---|---|---|---|---|---|
| June @ ≥30 sessions  | 97.9% | **+0.1241** | [−0.250, +0.498] | 188 / 57 | +0.3269 (159) |
| July @ ≥30 sessions  | 86.6% | **−0.6752** | [−0.813, −0.538] | 199 / 57 | −0.6155 (173) |
| August (immature, trajectory only) | 82.2% | −0.5427 | — | 134 | — |

Two mature cohorts at the SAME age gate disagree by **0.80R with non-overlapping CIs**. This is not
the resolution-speed artifact (both are past the winner-resolution window; July's exit mix is fully
developed) — it is **regime dependence across detection windows**. And June, measured to the end, was
never significant: its own CI spans zero.

**The June fixed-cohort curve rolled over:** 95.3% closed / +0.2129 (08-01) → 97.9% closed /
**+0.1241** (09-02). The last resolutions were breakevens and stops, not lingering winners. The
one direction read #2 called conservative (open winners lingering) did not materialize.

## 2. The pooled restatement at maturity, against the frozen 0026 primaries

| measure (age ≥30) | n | mean R | 95% CI | verdict vs zero |
|---|---|---|---|---|
| closed_only, pooled | 387 | −0.2869 | [−0.486, −0.088] | **negative, CI excludes 0** |
| mtm_at_horizon, pooled | 411 | −0.1864 | [−0.379, +0.007] | indeterminate by 0.007 |
| closed_only, non-ETF | 332 | −0.1642 | [−0.393, +0.065] | indeterminate |

Win rate at maturity: 96/387 = 24.8%, Wilson LB 20.8%. Favorable-reprice arm at maturity: −0.19.

**Under v2.2's banking rule (both primaries + CI clear of the boundary): NOT BANKED.** The two frozen
primaries disagree (closed-only clears; mtm misses by 0.007R), and the non-ETF composition spans zero.
**T4 stays UNDETERMINED — but asymmetrically: every mature estimate is ≤ 0 or indeterminate; none is
positive.** The A+-selectivity implication (a negative broad-watch validates the filter) is *leaning
supported* and remains unbanked.

**Method caveat, load-bearing:** the age-bracket table's gradient (pooled −0.40 at ≥0 improving to
−0.07 at ≥40) **confounds maturity with regime** — older brackets are increasingly June. The
per-cohort equal-age view above is the instrument; the pooled bracket gradient must not be read as
"it improves with age."

## 3. The ETF slice — the universe-composition question, sharpened

**57 mature closed ETF signals / 7 names / mean −1.0107 / ZERO winners** — every one died at
`initial_stop` (read #2: 38/6/−0.97/zero; the pattern extended without a single exception). The
watch pool as emitted contains a slice with unambiguously negative expectancy under this ruleset.
Still short of the V2.1 promotion gate (signals yes, 6 months no — data starts 06-05). **Re-check at
the December T10 checkpoint; until then it stays a flagged universe-composition finding, not a screen
change.**

## 4. The A+ arm — reported ONLY with the binding caveat (v2.2 OQ-3 line)

> **CAVEAT (binding, ruled 2026-08-25):** the shadow A+ arm's stop geometry is the ENTRY-BAR LOW; the
> live mandate doctrine stops at the FROZEN CANDIDATE STOP. The arm's mean (headline −0.593 closed,
> n=6) measures ITS OWN geometry, not the doctrine's.

The live-vs-shadow pair table is the evidence, and this month produced its sharpest instance:

| mandate | shadow twin R (entry-bar-low stop) | live outcome (mandate stop) |
|---|---|---|
| NVCR 06-18 | −1.000 stop | not taken (pre-latch posture) |
| AMN 07-01 | 0.000 breakeven | not taken |
| FTRE 07-20 | +0.443 breakeven | trade 19 closed −0.092 |
| AMN 08-03 | −0.558 open-mtm | trade 20 closed −0.996 (decayed-latch spike entry, not doctrine) |
| OII 08-10 | −1.000 stop | trade 25 OPEN, ≈−0.17 @ 09-01, stop intact |
| CADL 08-11 | **−1.000 stop** | trade 23 partial-exited, **≈+1.22R running** |
| RHI 08-13 | −1.000 stop | trade 24 OPEN, ≈−0.07 @ 09-01, stop intact |

CADL is a **sign flip on the same entry**: the shadow's entry-bar-low stop killed it at −1R while the
live mandate-stop position never approached its stop and is the book's best holding. Four of the last
four shadow A+ twins died at entry-bar-low stops while zero of the four live positions has stopped.
The stop-geometry divergence is SYSTEMATIC (banked 08-25) and the arm's mean is not a doctrine
expectancy estimate. (Divergence here is the OQ-3 class: the measured value of a rule difference,
not a parity anomaly.)

## 5. §3.2 log entry (appended to charter §7; duplicated here for the study record)

- Drumbeat: 23 artifacts / 23 NYSE sessions 08-01..09-02 — 100%; no T1.
- Funnel (newest): 5940 detections → 1188 unique signals → 0 unattributed. Delta since read #2: +2050 detections / +410 signals.
- Pricing: trigger 662/1045 broad-watch; priced closed N=588 signals / 125 unique names; scenarios closed_only 588 / mtm 662 / forced 662 / adverse 662 (artifact scorecard).
- Log maturity: detections 2026-06-05..2026-09-02 (60-session longest window); 227 distinct tickers; 168,092 forward observations (was 68,911).
- Live epoch record: 6 new trades since read #2 (22 ORKA `by_design` H2-fire OK; 23 CADL `standard` A+ OK; 24 RHI `standard` — mandate fill MISFILED as Broad-watch, correction pending; 25 OII `standard` A+ OK, label NULL-pending; 26 NRIX `by_design` H2-fire OK; 27 TVTX `standard` discretionary-watch OK). Intent contract: HELD on all six. Discipline tags: closed trades all `none_observed`; open trades untagged (assigned at review). **Two live exceptions named:** disc 103 (PBF, 2 sh untracked at broker, 09-02, unresolved — T6-adjacent, not a journaled trade) and ORKA's journal stop 96.27 gapped through 08-31 without execution (see the exit recommendation of the same date).
- Hypothesis progress: **H1 2/20 closed** (17 VSTS, 18 AMN) with FOUR named non-closed members: 19 FTRE (closed, MISFILED Broad-watch — correction executable NOW via the Demand C surface, same shape as correction 1), 20 AMN (closed, deliberate NULL pending Demand A), 23 CADL (open, labeled), 24/25 (open, corrections pending 22-A2). **H2 1/10 closed** (21 LQDA −0.32R) + 2 open (22, 26). H4 0/10. H3 closed-target-met (unchanged). H5 broad-watch: primary read is THIS study's §1-2 (shadow-measured per its registry row); live-labeled membership after excluding misfiled 19/24: one open trade (27).
- Tripwires since read #2: T3 ×4 glances (all adjudicated; spot-check cadence 5-of-10 maintained, numerator still 7); T5 ×6 fires (OII·CADL·RHI taken+filled; DFTX taken-resting; STTK UNKNOWN — operator question outstanding; IMNM live today). Post-epoch mandates now 12 (dedup: distinct ticker+pivot).
- **invalid_ohlc: 23 → 28 (08-01) → 69 (09-02), now 5.8% of signals vs 3.6% at read #2 — the RATE is growing, not just the count.** Research-health YELLOW (stoplight cannot escalate — standing finding). Not yet root-caused beyond the ragged-tail family; flagged as the read's one data-quality watch item.
- Posture: **UNCHANGED** — stop-engineering + market time. Nothing here originates engineering demand. The one recommendation is an operator ACTION with existing tools: run the trade-19 cohort correction (Demand C surface, citation = FTRE fire 07-20 candidates + daily_recommendations rows, which pre-date the 07-31 fill).

## 6. Methods (every number's source)

Ages: NYSE sessions via `exchange_calendars` XNYS, `sessions_distance(detection_date, 2026-09-01)−1` — one clock domain throughout. Closed = `exit_reason` set AND `open_at_horizon=False` in `results.csv`. mtm = all triggered rows (open rows carry mark R). CIs: normal approx, mean ±1.96·SD/√n. Wilson LB: z=1.96. ETF set: `candidates.industry='Exchange Traded Fund'` (52 tickers). Live DB read `mode=ro`, schema v36. No capital-cycle comparison across the correction-38 boundary appears in this read.
