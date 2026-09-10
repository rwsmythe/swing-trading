# 2026-09-09 — Quarterly strategic review #1 (watch standard §1; owed by read #3, paid here)

**Role:** Research Director (fifth generation). **Operator direction:** "Run the quarterly pass now" (2026-09-09, in-session).
**Scope (watch standard §1, quarterly tier):** re-validate the charter §6 standing recommendations top to bottom; restate the portfolio-growth framing; check the B-backlog gate (T9). Nothing here adjusts a criterion (§5) and nothing here commissions work.
**Why it is a standalone entry:** the standard sets the first quarterly pass at the third monthly read (early 2026-09). Read #3 (2026-09-02) carried the monthly items only; no §6 re-validation, no growth restatement, no pattern count against the N≥100 gate is recorded there or anywhere else. This pays it one week late.
**Evidence discipline:** every number below was queried fresh on 2026-09-09 (live DB `mode=ro`, schema v38; the engine artifact `20260910T034532Z` = run 173; the last eight manifests). The cited artifact's four ledger files are copied under `artifacts/` per watch standard v2.1.

---

## 1. T9 — the B-backlog gate

### 1.1 What the gate actually is

`research/phase-0-tasks.md` (B-1..B-8) points at the arc-closure predicates, `research/studies/2026-05-27-applied-research-arc-closure.md` §7. There are FIVE, met simultaneously:

1. Substrate scale: N ≥ 100 patterns per substrate.
2. Cohort fixture stability: frozen regeneration semantics.
3. At least one ruleset that passes all three discipline gates (CI lower bound positive with N ≥ 10 closed; no cohort substitution; substrate-freshness reproducibility).
4. Multi-substrate consistency: positive expectancy reproduces across ≥ 2 independent substrates.
5. Operator-approved revisit framing with pre-committed discipline gates.

The watch standard's T9 ("pattern count reaches 100") names predicate 1 only. The reads have never logged it.

### 1.2 The count, with its method

The temporal log holds **6,510 `pattern_detection_events` = 1,302 unique signals × 5 classes**: every signal gets one row per detector class regardless of whether the class matched (all five classes show exactly 1,302 events on the same 236 tickers). So a raw event count is a count of evaluations, not of patterns. **The pattern-instance definition used here: an event with `composite_score > 0`** (score 0 = the detector found no structure); reported at the distinct-name grain because re-detections of one name walk identical bars (read #1's correlated-sample rule). Maturity = a detection with ≥ 30 forward sessions (the v2.2 winner-resolution window).

| class | events with score > 0 | distinct names | names, score > 0 and ≥ 30 sessions | names, score ≥ 0.5 and ≥ 30 sessions |
|---|---|---|---|---|
| high_tight_flag | 719 | 149 | 93 | 66 |
| vcp | 238 | 75 | 45 | 4 |
| cup_with_handle | 108 | 29 | 17 | 14 |
| flat_base | 100 | 24 | 17 | 5 |
| **double_bottom_w** | **0** | **0** | **0** | **0** |

Detection span 2026-06-05..2026-09-10; all classes at `detector_version` `*@v1.0.0`, source `pipeline` only; per-detection forward depth: 702 detections at 60+ sessions, 2,918 at 30–59, 1,817 at 10–29, 948 under 10.

### 1.3 Verdict per predicate

| predicate | state | basis |
|---|---|---|
| 1 scale | **crossed on ONE substrate** (HTF: 149 names, 93 mature); VCP at 75 is on the way; CWH/FB are not; **DBW is at zero** | table above |
| 2 fixture stability | met by construction | the immutable log, pinned detector versions |
| 3 a ruleset passing all three gates | **NOT met** | the only priced ruleset is the operational one, via the shadow engine; its mature closed-only means are all ≤ 0 (read #3; tonight's artifact: A+ arm −0.590 n=7, broad-watch −0.376 n=655, near-A+ −0.400 n=11) |
| 4 multi-substrate consistency | unreachable while 3 fails | — |
| 5 operator-approved framing | none exists | — |

**T9 disposition: GATE-OPEN by scale on high_tight_flag only; the B-backlog is NOT commissionable.** The standard says a crossed T9 is evaluated against the yield picture, not auto-commissioned; the yield picture is unchanged (zero deployable rulesets). Predicates 3–5 are the ones that matter and none is close.

### 1.4 The finding underneath the count — the W-bottom detector has never fired

The B-1..B-8 backlog is the continuation of the W-pattern arc; its substrate is `double_bottom_w`. That detector has returned `composite_score = 0` on **all 1,302 signals over 66 sessions**, and the June exemplar-recall study already recorded it at **0/2 on documented exemplars under both single-session and window-sweep timing** (`research/studies/2026-06-08-minervini-exemplar-recall.md`, class table). A detector that fires nowhere, on exemplars included, is indistinguishable from a broken one, and its silence has been read as "no W-bottoms in the universe" by default for three months. Per my own standing rule (an instrument's silence is evidence only that it looked), this is a **candidate silent failure of the detector**, not a fact about the market.

This is not an edge claim and it is not a commission. It is a routing note: the detector lives in `swing/patterns/` (CHARC's lane), and any DBW-dependent research is blocked on a bounded diagnostic — does the v1.0.0 detector fire on ANY synthetic or historical W-bottom at all? Until that answer exists, predicate 1 for the W substrate reads N = 0, not "maturing."

---

## 2. Charter §6 standing recommendations — re-validated item by item

| item | 2026-06 text | today's evidence | disposition |
|---|---|---|---|
| **P1-NOW** broad-watch drumbeat | live, autonomous, stop-engineering | 100% session coverage since read #3; unattributed 0 on every run; accrual 1,188→1,302 signals in a week; newest artifact 0 days old | **HOLD, unchanged** |
| **P1** shadow-expectancy engine | the centerpiece; drives H1 at signal pace | the instrument matured into the convergence-curve read (v2.2). Its verdict today: T4 UNDETERMINED, asymmetric (every mature estimate ≤ 0 or indeterminate; the positive direction is the unsupported one). A+ arm n=7 priced, reported only with the stop-geometry caveat | **HOLD.** What changed since June is the read discipline, not the instrument. The engine cannot supply predicate 3; it can only tell us the operational ruleset does not pass it |
| **P0** entry_intent | closed | contract HELD on all 12 post-epoch trades (one deliberate NULL, trade 20, awaiting Demand A) | closed; nothing to revalidate |
| **P2** let the log mature; bounded funnel-wideners only | "N ≥ 100 months away" | scale is HERE on one substrate (§1.2) — the "months away" line is stale. But the B-backlog remains blocked on predicates 3–5, and the young-name primary-base screen is still depth-uncalibrated (the YHOO false-negative) | **HOLD with a text correction:** the constraint is no longer log maturity, it is the absence of any ruleset with demonstrated edge — which research validates and does not invent |
| **Do NOT** widen thresholds / size up / let plumbing absorb cycles | — | no threshold change shipped; sizing unchanged at the $7,500 floor; Phase 22 has been governance + provenance work (22-A/A3/A4) | **all three HOLD** |
| ETF universe-composition candidate (read #2/#3) | 57 closed / 7 names / zero winners | unchanged; lacks the 6-month gate | deferred to the December T10, as ruled |

**Two candidates for the §6 stack, neither engineering:**
- **The trail-doctrine contradiction** (advisory trails from `pre_+1.5R`; the eligibility flag says +2.0R MFE) is the one live §VII.F methodology question with a measurable answer: the shadow engine can price trail-from-entry vs trail-later across the priced cohort. RD-scoped read; the interim ruling (the eligibility gate governs) stands.
- **The stop axis** is where live and shadow diverge hardest (pairs N=3: FTRE trail timing; AMN agree; CADL a sign flip at the stop). A priced comparison of mandate-stop vs entry-bar-low geometry on the A+ arm is scopable from existing artifacts. Bank nothing at N=3; scope the read for October.

---

## 3. Portfolio-growth framing, restated on fresh numbers

| quantity | value | source |
|---|---|---|
| NLV at the epoch (2026-06-08..12) | $2,027.44 | `account_equity_snapshots` |
| NLV 2026-09-09 | $3,138.50 | snapshot 78, `schwab_api`, net_liq |
| deposits since the epoch | $1,300.00 (4) | `cash_movements`, kind=deposit, date ≥ 06-10 |
| out-of-framework outlays since the epoch | $574.62 (SPCX 06-15, RKLB 06-30) | `cash_movements`, kind=withdraw; their marks sit INSIDE NLV, outside the framework |
| framework trading, post-epoch, CLOSED (7) | realized **−$32.83**, sum **−1.54R**, mean −0.22R, 3 wins | `fills`, trades entered ≥ 06-10 with `current_size = 0` |
| … of which `standard` intent (4: VSTS, AMN-18, FTRE, TVTX) | +0.051 / +0.024 / −0.092 / +0.010 = **−0.007R** | same |
| … `by_design` H2 (2: LQDA, ORKA) | −0.322 / −0.216 = −0.54R | same |
| … NULL intent (trade 20 AMN) | −0.996R | same |
| framework trading, OPEN (5), marked at 09-09 closes | **−$21.14 / −0.23R** (CADL +0.81R, RHI −0.60R, OII −0.34R, NRIX −0.18R, PBF +0.07R) | `candidates.close` at data_asof 09-09 |

**The framing is unchanged from June, and it should be said plainly:** the account is growing on deposits. The framework's post-epoch contribution is about −$54 realized-plus-marked on a ~$3.1K base. The `standard` cohort has produced four scratches and has not yet tested the thesis; H1 stands at 2/20 closed. Nothing in the live record, the shadow engine, or the temporal log demonstrates edge in any cohort. The asset to build is still a statistically credible positive expectancy on rule-followed signals, and the current evidence on the operational ruleset points the other way at maturity (read #3). Capital scaling before that exists would scale a negative number.

---

## 4. Items found during the pass (not part of the quarterly checklist; recorded so they are not lost)

1. **RHI (trade 24, `standard`): the journal stop was reconciled DOWN to the broker's.** `reconciliation_corrections` 41 (2026-08-25) moved `current_stop` 34.77 → 34.18, i.e. the broker stop sits $0.59 (6.3%) below the framework's initial stop; the daily-management records carry 34.18 unchanged since. A reconciliation correction on a `standard` trade is the T6 shape, and I find no adjudication of it in the record. **Intent unverified — a question to the operator, not a verdict.**
2. **Read #3's H2 line undercounts.** It logged "H2 1/10 + 2 open"; the registry reader (`swing hypothesis list`) reads 3/10 today, and trades 14 (pre-epoch) and 21 (closed 08-12) were both closed before 09-02, so the correct 09-02 figure was ≥ 2/10 (ORKA's 08-27 stop fill makes it 3/10 depending on when the fill was recorded). Corrected in the charter §7 entry that accompanies this study.
3. **`invalid_ohlc` is flat at 69** across all seven manifests since 09-02 (the climb paused; the watch stands; the stoplight still cannot escalate it).
4. **H3's registry row shows `TRIPWIRE FIRED`** on `closed-target-met` — known and banked (the designed-negative cohort), noted so the next reader does not rediscover it.

---

## 5. Recommendations (for the operator; nothing here is self-executing)

1. **No B-backlog commission.** T9 is crossed by scale on one substrate and the arc's own predicates 3–5 are unmet. Posture stays STOP-ENGINEERING + MARKET TIME.
2. **Route the DBW-never-fires question to CHARC** as a bounded detector diagnostic (does `double_bottom_w@v1.0.0` fire on any known W-bottom?). It is his lane, it is cheap, and every W-substrate question downstream is blocked on it. I will post it on your word.
3. **RHI stop (item 4.1): state the intent** so it is either a documented decision or a T6 call-out; I will record whichever it is.
4. **Charter text refresh at direction:** §5's "months away" and §6 P2's "N ≥ 100 months away" are stale as of this pass; the correction is one sentence each (mine to make; docs-only).
5. **October read scope additions:** the stop-axis pair read and the trail-doctrine priced comparison (§2), both from existing artifacts; and the T9 line becomes a standing row in the §3.2 log entry from read #4 on, reported with the method in §1.2.
