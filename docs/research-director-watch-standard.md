# Research Director — Data-Collection Watch Standard

**Version 1 — adopted 2026-06-10 (operator-commissioned as part of the training-epoch contract).**
**Owner:** the research-director/evaluator role (`docs/research-director-context.md` §1). Any instance of that role
is BOUND by this standard; amendments are deliberate (a new dated version section, operator-acknowledged), never
silent drift.
**Where reads are logged:** the charter §7 session log (append-only), using the §3.2 entry format below — so every
future instance can reconstruct the watch history without re-deriving it.

**What is being watched (the four accruing streams):**
A. The shadow-expectancy nightly drumbeat (funnel + scorecard artifacts under `exports/research/shadow-expectancy-*/`).
B. Temporal-log maturity (forward-observation depth; pattern count toward the B-backlog N≥100 gate).
C. The live trade record, NEW EPOCH ONLY (`standard`-intent cohort + the epoch-integrity tripwires; epoch boundary
   2026-06-10 per the charter §7 epoch entry — the 16 pre-epoch trades are settled tuition, never re-read as practice).
D. Pre-registered hypothesis progress (H1 20 / H2 10 / H4 10 closed-labeled; broad-watch baseline N≥30 PRICED SHADOW
   signals, authoritative in the engine `summary.md`, NOT the DB progress surfaces).

---

## §1 Cadence (the periodicity answer)

| Tier | Period | Executor | Effort | Purpose |
|---|---|---|---|---|
| **Weekly glance** | every Friday (or the last trading day of the week) | the OPERATOR (mechanical checklist §2; no research-director session needed) | ~5 min | detect a silently-dead drumbeat or a funnel regression within days, not weeks |
| **Monthly read** | first trading week of each month — **the binding evaluator cadence** | a research-director instance | ~30–60 min | the substantive read (§3): accrual trends, epoch integrity, hypothesis progress, posture re-validation |
| **Quarterly strategic** | every 3rd monthly read (first: early 2026-09) | research-director instance (folded into that month's read) | +30 min | re-validate the standing recommendations top-to-bottom; portfolio-growth framing; B-backlog gate check |
| **Event tripwires** | immediate, schedule-independent | whoever sees it (operator escalates; research director acts) | per §4 | the table in §4 — conditions with prescribed actions |

First monthly read due: **first trading week of July 2026.** A research-director instance spun up between monthly
reads for any other purpose MUST run the §3 checklist first if more than ~2 weeks have passed since the last logged
read (catch-up discipline).

---

## §2 The weekly glance (operator-executable, mechanical)

1. The newest `exports/research/shadow-expectancy-*/summary.md` is from the last trading session (drumbeat alive).
2. In it: `total_unattributed = 0` (any nonzero → §4 T2).
3. `unique_signals` is moving across the week (the log is accruing).
4. Trigger rate numerator: still `0/N`, or has the FIRST breakout priced? (nonzero → §4 T3 — good news, but gated.)
5. If any live trade was entered this week: it carries the intent label per the epoch contract (charter §7) and no
   risk/reconciliation tag landed on a `standard` trade (else → §4 T6).

Anything anomalous → message the research director with the artifact path; do not wait for the monthly read.

---

## §3 The monthly read (binding checklist)

**Evidence discipline:** every number below is read FRESH from the live DB (`mode=ro`) and the artifact files —
never carried forward from a prior read, a return report, or memory (`feedback_no_false_green_claim`,
`feedback_adversarial_review_verify_data_shapes`).

### §3.1 Checklist

1. **Drumbeat integrity:** artifact dirs exist for ~every trading session since the last read; spot-open the newest
   `summary.md` + `manifest.json`. Gaps → §4 T1.
2. **Funnel:** detections / unique signals / unattributed breakdown vs the last read's logged numbers. Unattributed
   must be 0; the signal count's growth rate is the accrual pulse.
3. **Pricing progress:** trigger rate (n triggered / n attributed-reaching-simulation), priced terminal count per
   censoring scenario, **priced N vs the broad-watch N≥30 decision gate**. First priced trade → §4 T3 if not yet done.
4. **Log maturity:** oldest detection date → newest observation date (the longest forward window, in sessions);
   distinct pattern count vs the **N≥100 B-backlog gate**.
5. **Live record, new epoch only:** trades entered since the last read — intent labels vs the epoch contract
   (charter §7: A+→`standard`; H2/H4 fires→the only legit `by_design`; discretionary→`standard` or not at all);
   the trade-process card `standard` facet + the always-on execution-discipline panel (any risk/recon tag on a
   `standard` trade → §4 T6); `CHASED`/`NO_SETUP` on `standard` trades → §4 T7.
6. **Hypothesis progress:** H1/H2/H4 closed-labeled counts (DB) + broad-watch priced N (`summary.md`). Any
   pre-registered decision criterion within reach → schedule the decision read (§5).
7. **Standing-recommendation re-validation:** does anything observed change the charter §6 stack? (Default answer
   after the 2026-06 build-out: NO — the posture is stop-engineering + market time. Deviating from that default
   requires written justification in the log entry.)

### §3.2 Standard log-entry format (append to charter §7)

```
### YYYY-MM-DD — monthly watch read #N (standard vN)
- Drumbeat: <sessions covered>/<expected>; gaps: <none|list>.
- Funnel (newest): <detections> -> <signals> -> <unattributed> unattributed. Delta since read #N-1: <+signals>.
- Pricing: trigger <k>/<n>; priced N=<n> (gate 30); scenarios <closed_only n / mtm n / forced n / adverse n>.
- Log maturity: longest window <S> sessions; pattern count <P> (gate 100).
- Live epoch record: <T> new trades; intent contract: <held|violated (detail)>; discipline panel: <clean|tags>.
- Hypothesis progress: H1 <x>/20, H2 <x>/10, H4 <x>/10, broad-watch priced <x>/30.
- Tripwires fired since last read: <none|T-ids + actions taken>.
- Posture: <unchanged|changed + justification>.
```

---

## §4 Event tripwires (condition → action; immediate, not calendar-bound)

| ID | Condition | Severity | Prescribed action |
|---|---|---|---|
| **T1** | No shadow-expectancy artifact for >2 consecutive trading sessions | HIGH | Operational break — commission a Phase 16 fix (pipeline.log + `pipeline_step_timings` + `warnings_json` are the diagnostic surfaces). Do NOT let it ride to the monthly read. |
| **T2** | `total_unattributed > 0` in any nightly funnel | HIGH | Same-session investigation. `multi_match > 0` = the matcher fallback gate regressed (worst case — narrow-cohort cannibalization); `matched_no_hypothesis > 0` = a registry/status change or a new population leak; `no_candidate_join > 0` = a join regression. Root-cause before any other action. |
| **T3** | The FIRST priced shadow trade appears | POSITIVE-GATED | One-time golden gate: hand-walk that single trade end-to-end (entry bar `high >= candidate.pivot`, fill = `max(pivot, open)`, stop = entry-bar low, partial/trail/exit per ruleset) against the raw forward bars BEFORE trusting any accrual. Log the verification. Subsequent priced trades: spot-check 1-in-5 until N=10, then trust the machinery. |
| **T4** | Broad-watch priced N reaches 30 | DECISION | Run the pre-registered decision read EXACTLY as frozen in the 0026 registry row (realistic arm; closed_only + mtm_at_horizon primary; mean R + Wilson-LB across all four scenarios). Write a study doc under `research/studies/`; recommendation flows from the frozen criteria, not vibes. Negative/zero = bankable validation of A+ selectivity; positive = cohort-refinement research, NOT deployment. |
| **T5** | A live A+ fire occurs | MEDIUM | Confirm the operator took/logged it `standard`-intent per the epoch contract (or documented why not). H1 is the money question and remains sample-starved — each fire is precious. |
| **T6** | Any risk/reconciliation tag on a `standard`-intent trade | MEDIUM | Blunt call-out at once (not deferred to the monthly read). This is the exact slip class the epoch declaration retired; the discipline panel pins it. |
| **T7** | A `by_design` trade that is NOT an H2/H4 program fire, OR `CHASED`/`NO_SETUP` on a `standard` trade | MEDIUM | The epoch declaration is failing — name it plainly, cite the contract, ask the operator for the intent story (verify before labeling a mistake — then be direct). |
| **T8** | Any registered hypothesis's loss tripwire fires on live-labeled trades | HIGH | Recommend an entry pause for that cohort per the registry's own design; evaluate before more samples. |
| **T9** | Temporal-log pattern count reaches 100 | GATE-OPEN | The B-1..B-8 backlog becomes commissionable. Do not auto-commission — evaluate against the then-current yield picture first. |
| **T10** | Calendar: 2026-12 (the standing P2 ~6-month checkpoint) | SCHEDULED | Full strategic review of the temporal-log program even if no other gate fired. |

---

## §5 Pre-registered decision points (do not re-derive; do not adjust mid-stream)

- **Broad-watch baseline:** N≥30 priced shadow signals → the frozen 0026 criteria. (T4)
- **H1 A+ baseline:** 20 closed labeled trades → mean R > 0 AND Wilson-LB win rate > 30% (frozen 0008).
- **H2 / H4:** 10 closed each → frozen 0008 criteria.
- **B-backlog gate:** N≥100 temporal-log patterns. (T9)
- Criteria amendments route through V2.1 §VII.F governance (a new migration), exactly as the broad-watch amendment
  did. A watch read NEVER adjusts a criterion.

## §6 Consistency rules for future instances

1. Read this standard at session start alongside the charter (the charter §6 links here).
2. Evidence before assertion — every logged number freshly queried.
3. Log every read in the §3.2 format; the log is append-only.
4. The default posture is STOP-ENGINEERING + market time; deviations need written justification.
5. Amend this standard only by a new dated version section, operator-acknowledged.
