# RD — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** This is the one always-current state pointer for the RD (Research Director / CIO) role. The dated session log in [`docs/research-director-context.md`](research-director-context.md) §7 is APPEND-ONLY history; current state lives HERE only. Bootstrap reads this file FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

---

**Last overwritten:** 2026-07-03 (monthly watch read #1 EXECUTED = the **T4 broad-watch decision read**; T3 AMN spot-check PASS). **Program state:** **T4 VERDICT = PROVISIONAL-NEGATIVE — bankable validation of A+ gate selectivity** (study `research/studies/2026-07-03-broad-watch-baseline-t4-decision-read.md`): broad-watch closed-only realized mean R **−0.648** (n=97 signals / 36 names; win 10.3%, Wilson-LB 5.7%); the +0.680 mtm is NOT bankable (survivorship censoring + risk-unit artifact + 165/165 ambiguous-flag optimism — every bias points UP, so the negative verdict is conservative-robust; adverse scenario ≈0). Shadow win rate 10.3% reproduces the pre-epoch live 12.5% — two independent paths agree the unfiltered watch pool loses. NO deployment, NO criterion change, cohort-refinement branch NOT triggered (only unrealized numbers are positive). **CONFIRMATORY re-read PRE-COMMITTED on the first post-Phase-19-fix artifact** (engine pure-recompute → retroactive; expected direction: closed mean more negative). Posture = **STOP-ENGINEERING + market time** (unchanged). Schema v31; local-only commits ahead of origin (operator push cadence; do not push).

## Live workstreams / arcs in flight
- **T4 confirmatory re-read — PRE-COMMITTED, blocked on the Phase-19 shadow-engine fix** (risk-unit floor / ambiguous-entry gate; CHARC-queued `3f4b5236`, operator-folded 06-30, thread `shadow-engine-risk-unit-artifact`). New evidence from read #1 for the fix spec (posted CHARC): the `entry_bar_ambiguous` flag is **degenerate — 165/165 of the broad-watch priced population** (stop=entry-bar-LoD ⇒ same-bar stop-touch always possible), so "gate the flagged signals" as scoped would gate EVERYTHING — the fix needs a risk-unit floor and/or a real discriminator, not the current flag; top open marks PGNY +18.9R / DFTX +13.5R / LTH +10.5R are the artifact class. RD reviews the fix's measurement semantics at merge, then runs the confirmatory read.
- **coverage_gaps CALIBRATION-C delisting gap — flagged CHARC** (`20260702T044056Z`, thread `coverage-gaps-calibration`): CNTA delisted → trailing skip-warning holes counted (clause-1 wrongly gates 2b) → false-RED, growing daily (60 @ 07-02 → 100 @ 07-03 monitor read). MY design gap; fix = accept 2b regardless of clause-1. RD reviews at the fix. Do NOT read the current coverage-RED as a real failure (drumbeat healthy; #1 finiteness GREEN).
- **#5 drumbeat false-RED — PARKED** (offender = manual worktree launches, operator-pinned 06-27; root+guard fix banked `19185b04`; revisit next weekend per operator; observe-first).
- Standing watch cadence otherwise. **Monthly read #2 due first trading week of August 2026** (or fold into the confirmatory read if Phase-19 lands first). Quarterly strategic = the September read.

## Pending RD decisions (operator-sequenced)
- None owed by RD. (T9 pattern-count operationalization flagged for a DELIBERATE definition at a future read — matured-forward-walk reading = 46 det / 10 signals vs gate 100; raw readings already >100. Not urgent.)

## Closed recently
- **T4 broad-watch decision read #1 — EXECUTED 2026-07-03** (see Program state). Monthly read #1 logged in charter §7 (§3.2 format); all checklist items clean except the known benign coverage-RED.
- **T3 spot-check AMN A+ (07-01, det run 116) — PASS:** engine-exact to 4dp (fill 33.48 = max(pivot,open), LoD stop 32.35, risk $1.13 = 0.78×ATR — SANE, not the VSTS class); bars verified vs independent yfinance to the cent; obs rows written post-close. A+ cohort = 3 signals ever (NVCR untriggered / VSTS artifact / AMN clean). The 1-in-5-until-N=10 spot-check discipline continues on new A+ priced signals.
- **2026-06-30 T3 spot-check** caught the VSTS +27.333R risk-unit artifact → CHARC Phase-19 queue (mtm decayed to +17.78 by 07-02; still untradeable-stop fabrication). **Do NOT trust the A+ mtm headline until the fix.**
- **coverage_gaps CALIBRATION C** MERGED `83c21305` (06-25); the 06-24 missed-run RED class resolved (842 accepted-historical). The delisting gap above is the successor issue.

## Watch-standard / tripwire status (T1–T7 + gates) — as of 2026-07-03
- **T4 — FIRED + READ EXECUTED** (this read; provisional-negative, confirmatory pending Phase-19). **T3 — AMN PASS** (spot-check cadence continues to N=10 priced A+; currently 2 priced). **T5 ×2 honored** (VSTS 06-25 + AMN 07-01, both `standard`/A+ `managing` — the FIRST live H1 accrual of the epoch; H1 = 1/20 closed +2 open). No T1/T2/T6/T7/T8. **T9 pending** (matured reading 46/100). **T10** = 2026-12.
- **Research-health monitor: overall RED = the KNOWN CNTA calibration gap (benign; fix flagged).** #1 finiteness GREEN (0 post-baseline of 13,116); #2 YELLOW `invalid_ohlc` 38 vs baseline 23 (+15, climbing — likely delisting-degenerate bars; watch, don't act); #4/#5/#6/#7 GREEN.
- Live record: 2 open `standard` A+ trades (VSTS ~+8% winner on operator's own entry/stop; AMN entered 07-01). Epoch intact.

## Behavioral load-bearing (pointers into the charter)
- Blunt over sycophantic; evidence before assertion (every number freshly queried from the live DB / artifacts — never carried forward). Verify intent before labeling a mistake, then be direct.
- QA the DIVERGENCE, never defend the brief (directive #10). Ground operational claims in `file:line` / on-disk reads (directive #9). A brief's "≈" between two production figures is the highest-risk line — verify vs LIVE values; tests real-derived, never premise-constructed.
- Front-load the merge-blocking L-checklist EARLY; when a CHEAP fix closes the exact failure class an arc exists to kill, push for the fix.
- Commissioning briefs crossing a CHARC §3 tripwire route through CHARC pre-dispatch (`harness-architecture.md` §5). RD is merge-blocking on measurement integrity; CHARC challenges measurement locks through the operator, not by override.
- Default posture: STOP-ENGINEERING + market time. Deviations need written justification.
- Weight REALIZED (closed-only) over marks in every expectancy read; when primary scenarios disagree in sign, the pre-committed realized read binds (T4 read #1 precedent).
