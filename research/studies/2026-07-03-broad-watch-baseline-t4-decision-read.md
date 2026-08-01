# Broad-Watch Baseline — T4 Pre-Registered Decision Read (N≥30 gate)

**Canonical citation:** "2026-07-03 broad-watch T4 decision read" (watch-standard §4 T4; hypothesis registry id 5, frozen at migration 0026, 2026-06-09).

**Status:** READ EXECUTED 2026-07-03 (monthly watch read #1). Verdict **PROVISIONAL-NEGATIVE — bankable validation of A+ gate selectivity**, pending one pre-committed confirmatory re-read after the Phase-19 shadow-engine risk-unit/ambiguous-entry fix (retroactive by pure recompute; see §6).

**Headline finding:** At priced N = 165 shadow signals / 48 unique names (gate: 30), the broad-watch baseline's **realized (closed-only) expectancy is decisively negative: mean R = −0.648 (n=97 closed signals / 36 names), win rate 10/97 = 10.3%, Wilson-LB 5.7%**. The positive unrealized mark (mtm_at_horizon +0.680) is dominated by three identified upward biases and is not bankable. Under the frozen 0026 criteria, negative-or-zero mean R = **bankable validation of A+ gate selectivity** — the unfiltered watch pool, mechanically traded by the full operational ruleset, loses money at signal-pace, independent of operator execution.

---

## §1 Pre-registered frame (frozen; not adjusted at read time)

Registry id 5 (`hypothesis_registry`, migration 0026, created 2026-06-09), decision criteria verbatim:

> SHADOW-measured (not closed live trades): primary read = realistic bracket arm on the closed_only and mtm_at_horizon censoring scenarios at N>=30 priced shadow signals; report mean R + Wilson lower-bound win rate across all four censoring scenarios. Pre-registered as a BASELINE: negative or zero mean R is a bankable validation of A+ gate selectivity; positive mean R triggers cohort-refinement research (which miss-sets carry the edge), NOT direct deployment.

Additional pre-commitments in force at read time:
- Watch-standard §3.1 item 3: report priced N at BOTH signal level and unique-name level (correlated re-detections).
- RD state pointer, logged 2026-06-17 — **before** these numbers existed: "At the T4 read, weight closed-only realized, not the blended number."

## §2 Data (all freshly read 2026-07-03; artifact `exports/research/shadow-expectancy-20260703T020948Z/`, live DB `mode=ro`)

Engine run 2026-07-03T02:09Z (data through session 2026-07-02). Funnel: 1765 detections → 353 unique signals → 0 unattributed.

**Broad-watch baseline, realistic bracket arm (the primary arm):**

| Scenario | n | mean R | wins | win rate | Wilson-LB |
|---|---|---|---|---|---|
| **closed_only** | **97** | **−0.648** | 10 | 10.3% | **5.7%** |
| **mtm_at_horizon** | **165** | **+0.680** | 72 | 43.6% | 36.3% |
| forced_exit_at_horizon_open | 165 | +0.680 | — | (≡ mtm at this log boundary) | — |
| stop_level_adverse | 165 | **+0.013** | — | (per-signal values not emitted in artifact; mean from summary.md) | — |

Favorable arm (secondary): closed_only −0.586; mtm +0.717.

- Priced N = **165 signals / 48 unique names** (gate 30 — crossed at both levels). Closed cohort = 97 signals / 36 names.
- Exit reasons (all priced): initial_stop 79, breakeven_stop 16, ma_close_below 2, horizon_mtm (open) 68.
- Correlation structure: 21 names carry >1 closed signal; the heaviest are **TNA ×11, URTY ×11, UDOW ×4 — 3× leveraged index ETFs, 26/97 (27%) of the closed cohort** (30/165 of priced), i.e. essentially one leveraged-index bet class re-detected across sessions. Effective independent N is materially below 97, but the gate crossing is unambiguous at any de-duplication.
- A+ baseline (for contrast, NOT this read's subject): 3 signals ever (NVCR 06-18 untriggered; VSTS 06-25; AMN 07-01), closed n=0, mtm n=2 mean +9.451 — **artifact-contaminated (VSTS +17.78R, the flagged risk-unit artifact) — do not trust** (charter §7 2026-06-30; CHARC Phase-19 queue).

## §3 Data-quality annotations (established during this read; none alter the frozen criteria)

1. **Risk-unit artifact class extends into the broad-watch open marks.** Top open marks — PGNY +18.88R, DFTX +13.47R, LTH +10.53R, ARMK +7.91R×4 — are the same collapsed/optimistic-tight risk-unit class flagged 2026-06-30 on VSTS (thread `shadow-engine-risk-unit-artifact`). These inflate the mtm scenario only.
2. **`entry_bar_ambiguous=True` on 165/165 priced signals — the flag is degenerate on this population.** By construction: stop = entry-bar LoD, so a same-bar stop-touch is always possible from daily bars; the engine resolves optimistically (entry survives the bar). The planned exclude-ambiguous sensitivity is therefore vacuous, and the optimism is a systematic **upward** bias on the whole scorecard.
3. **Closed-cohort spot-walk (TVTX 06-12, the largest closed winner +7.84R):** pivot 49.68, entry-bar low 48.98 → risk $0.70 (1.4% of entry). The underlying move is real (49.68 → ~55.2, +11%); the R is amplified by an optimistically tight stop but is not a fabrication (contrast VSTS's ~$0.04). Same class, milder degree.
4. **Bias direction is uniform.** Survivorship censoring (losers realize −1R quickly and leave to the closed cohort; winners linger open at marked run-ups), the risk-unit artifact (inflates winners' R; stop-outs pinned at −1R regardless), and ambiguous-entry optimism ALL push the measured numbers UP. The true tradeable-stop baseline is ≤ the measured one. **The negative verdict is conservative-robust; the positive mtm is not.**
5. Independent bar verification: the AMN A+ hand-walk this session (charter §7, 2026-07-03) matched engine arithmetic to 4 decimals and the temporal-log bars to the cent against a fresh yfinance fetch; observation rows written post-close. The measurement substrate is sound; the artifact is in the stop-derivation semantics only.

## §4 Adjudication under the frozen criteria

The two primary scenarios disagree in sign (closed −0.648 vs mtm +0.680); the frozen text does not specify the combination rule. Adjudication follows the 2026-06-17 pre-commitment (weight closed-only realized), which is independently forced by §3: every identified bias inflates mtm and none deflates it, and the adverse scenario bounds the open cohort's locked-in contribution at ≈ zero (+0.013 blended — if every open position stopped at its current stop today, the baseline is flat). A mark is not money; 68/165 of the cohort is unrealized.

**Realized read: NEGATIVE.** Mean R −0.648, win rate 10.3% (Wilson-LB 5.7%), n=97/36 names. Under the frozen rule: **negative-or-zero → bankable validation of A+ gate selectivity.** The positive-branch trigger (cohort-refinement research) is NOT met: the only positive number is unrealized and bias-dominated. If the open cohort later closes green at scale under the fixed engine, the refinement branch re-opens at the confirmatory read (§6) — that is the pre-registered branch properly applied at realization, not at mark.

**Convergent evidence:** the shadow-measured watch-pool win rate (10.3%) reproduces the operator's pre-epoch live record on the same population class (12.5%, 2/16, dominated by watch-pool entries — charter §3). Two independent measurement paths — hand-trading and mechanical signal-pace shadow — agree: the unfiltered watch pool loses. This is exactly the result the A+ gate exists to produce, and it retires the alternative explanation "the operator's negative record was execution, not selection."

## §5 What this does and does not establish

- **Establishes:** the broad watch pool, traded mechanically by the full operational ruleset, has negative realized expectancy at signal-pace (subject to §6 confirmation). A+ selectivity is doing real work at the gate boundary. The 2026-06-10 training-epoch tuition read is corroborated by machine evidence.
- **Does NOT establish:** anything about H1 (A+ positive expectancy) — the A+ shadow cohort is 3 signals / 0 closed, and live standard-cohort A+ trades are 2, both open ('managing'). H1 remains the money question and remains sample-starved. A+ supply observed at ~1/week (3 in 3 weeks) — the H1 decision is months out on both live and shadow paths.
- **Does NOT trigger:** deployment of anything, any criterion adjustment, or (yet) cohort-refinement research.

## §6 Pre-committed follow-up (the confirmatory read)

The Phase-19 shadow-engine fix (risk-unit floor / ambiguous-entry gating; CHARC-queued, operator-folded 2026-06-30) changes the stop-derivation semantics for the entire scorecard. The engine is pure-recompute (read-only, fresh artifact per run — CHARC code-trace 2026-06-30), so the fix is retroactive by re-run. **Pre-commitment:** re-execute this read on the first post-fix artifact as the CONFIRMATORY read of the same frozen criteria. Expected direction: floored/gated risk units shrink winners' R while stop-outs stay −1R → the closed-only mean moves further negative; reversal risk of this verdict is low. Until then this verdict is PROVISIONAL-NEGATIVE (banked, direction robust, magnitude approximate).

**Observation for the refinement axis (recorded, not commissioned):** 27% of the closed cohort is 3× leveraged index ETFs (TNA/URTY/UDOW) — instruments outside the methodology's stock-selection frame that entered via the #23-widened watch pool. Any future cohort-refinement pass should treat instrument-class composition as a first split. Whether the widened pool SHOULD contain leveraged ETFs at all is a population-design question for the operator + CHARC (measurement-lane observation only; the baseline read is honest either way — this is the population the log contains).

## §7 Provenance

- Artifact: `exports/research/shadow-expectancy-20260703T020948Z/` (summary.md + results.csv; engine run on data through 2026-07-02).
- Registry: `hypothesis_registry` id 5 (migration 0026, frozen 2026-06-09).
- Live DB reads: `~/swing-data/swing.db` mode=ro, 2026-07-03.
- Wilson LB: two-sided 95% (z=1.96) score interval, computed from per-signal rows in results.csv.
- Bias/artifact chain: charter §7 entries 2026-06-30 (VSTS artifact), 2026-07-03 (AMN clean walk); CHARC thread `shadow-engine-risk-unit-artifact` `20260630T012011Z`.
- Read executed by the RD role (monthly watch read #1, watch-standard v2 §3); logged in charter §7 in the §3.2 format.

---

## §8 CONFIRMATORY RE-READ — 2026-07-05 (the pre-committed §6 follow-up)

> **WITHDRAWN 2026-08-01. THE VERDICT BELOW IS NO LONGER SUPPORTED.** A fixed-cohort longitudinal series (the June detections measured against successive nightly artifacts) shows this same cohort moving **−1.0000 → +0.2129 purely by aging**, with the −0.6370 below sitting on that curve at **58.8% closure**. Both §4 and §8 were measuring **how fast losers resolve**, not expectancy. **T4 is UNDETERMINED**; the replacement estimate is positive but not bankable. See [`2026-08-01-t4-maturity-withdrawal/README.md`](2026-08-01-t4-maturity-withdrawal/README.md). The text below is PRESERVED as the historical record of what was read on 2026-07-05 and why — it is not a live verdict.


**Artifact:** `exports/research/shadow-expectancy-20260704T223859Z/` — the first full-corpus run on the 19-D-hardened engine (merged `f1add34c`; risk-unit floor 0.15 ADR-ratio, epsilon reader-clamp 1.0%, RD-ruled constants verified shipped). Same frozen 0026 criteria, same method as §2.

| Scenario | Read #1 (pre-fix, 07-03) | Read #2 (post-fix, 07-05) |
|---|---|---|
| closed_only | −0.648 (n=97/36 names; win 10.3%, LB 5.7%) | **−0.637 (n=100/39 names; win 11.0%, LB 6.3%)** |
| mtm_at_horizon | +0.680 (n=165) | +0.551 (n=171/53 names; win 43.3%, LB 36.1%) |
| forced_exit | +0.680 | +0.551 |
| stop_level_adverse | +0.013 | **−0.057** |

**VERDICT: CONFIRMED-NEGATIVE — the §4 banked result is now FINAL, not provisional.** The realized read is stable under the healed engine (−0.648 → −0.637; the small move is composition — 3 recovered closed signals entered, collapsed-risk names left). The adverse scenario flipped negative. The mtm dropped 0.680 → 0.551 exactly as the §3 bias-removal analysis predicted. The A+ headline healed to +1.124 (n=1) — **literally the hand-walked AMN value from the §3.5 verification: the measurement now equals the honest walk.** Every §3 artifact-class pathology is resolved: VSTS excluded as `degenerate_risk` (5 total incl. the ARMK cluster); `invalid_ohlc` 38 → 22 (16 ragged-walk signals recovered, +6 into the priced set, the rest honestly never-triggered/other); the 15-bar clamp census matches the §3 probe exactly (CALY excluded above-threshold).

**Honest annotations:** (1) PGNY 06-26 (+18.88 mtm) SURVIVES at ratio 0.164 — legitimately above the 0.15 floor (13¢ risk / $0.79 ADR; a real +9% move, thin-but-lawful stop). Marks in the 0.15–0.2 ratio band still amplify; WATCH whether any close into the realized cohort at inflated R — that is realized evidence for a future calibration, NOT grounds to re-tune the frozen setup now. (2) DFTX/LTH large marks are real moves with sane denominators (by design, not artifacts). (3) H1 unchanged: A+ closed n=0; the money question stays open on market time.

**Consequence:** the cohort-refinement branch remains untriggered; A+ gate selectivity validation is BANKED FINAL. Posture: stop-engineering + market time.
