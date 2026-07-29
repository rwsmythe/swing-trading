# RD — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** The one always-current state pointer for the RD (Research Director / CIO) role. The dated log in [`docs/research-director-context.md`](research-director-context.md) §7 is APPEND-ONLY history; current state lives HERE only. Bootstrap reads this FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

---

**Last overwritten:** 2026-07-29 — **GENERATIONAL HANDOFF at context capacity, mid-Phase-21.** Everything durable is committed; nothing load-bearing lives only in a mailbox (swept). Phases 19 and 20 CLOSED; Phase 21 in flight. Schema **v32**. Main is local-only ahead of origin — **the operator pushes; do NOT push.**

---

## 1. PROGRAM STATE — read before quoting any number

**T4 (broad-watch baseline) — the headline result, and it has SOFTENED. Do not repeat the old number.**

- Read #1/#2 verdict: CONFIRMED-NEGATIVE, closed-only **−0.648 → −0.637 (n≈97–100)**. Study: `research/studies/2026-07-03-broad-watch-baseline-t4-decision-read.md` (its 4 cited artifacts are git-tracked under the study's `artifacts/` per watch-standard **v2.1** cite=commit).
- **As of 2026-07-29 the cohort is n=312 and the closed mean is −0.2016.** Diagnosed as BOTH: (a) leveraged-ETF **dilution** — TNA/URTY/UDOW unchanged at ≈−1.0 but fell **27% → 10%** of the cohort; (b) the **non-ETF cohort genuinely improved −0.497 → −0.121**, win rate **10.3% → 22.1%**.
- **Likely mechanism: the unwinding of the survivorship bias read #1 itself identified** — losers realize −1R fast and leave to the closed set while winners linger open, so a young closed-cohort is biased NEGATIVE and rises as winners close.
- **Consequence: direction holds, the frozen positive-branch criterion is NOT met, nothing flips — but the margin thinned by two-thirds and the non-ETF slice is NEAR BREAK-EVEN.** "The watch pool loses money" may be closer to "it roughly breaks even, and the leveraged-ETF slice loses" — which makes the A+-selectivity validation weaker than banked.
- **The "FINAL" label attached 07-05 oversold stability** — it meant *survived the engine fix*, not *the cohort is closed*. **Read #2 must RE-STATE the verdict at the larger N, not restate read #1.**

**H1 (the money question) = 2/20 closed, standard-epoch.** VSTS +$1.80; AMN +$1.17 (D25-corrected). A+ **shadow** cohort: NVCR −1.0R closed, AMN 0.0R closed, VSTS-1 excluded `degenerate_risk`, FTRE open **+1.66R**, VSTS-2 never_triggered. A+ supply ≈ 1/week; **5 fires ever.**

**Posture: STOP-ENGINEERING + MARKET TIME.** Both measurement chains are forensically hardened and witnessed (research chain Phase 19; trading ledger Phase 20 / D25). The weeknight scheduler runs unattended at 17:30 HST.

**Health 2026-07-29:** research-health ALL SEVEN GREEN post-v32; `invalid_ohlc` still exactly baseline 23; drumbeat artifact 0 days old; 730 signals; unattributed 0.

## 2. LIVE TRADING STATE

- **FTRE latch ARMED** — fire 2026-07-20; frozen pivot **18.34**; frozen invalidation **14.88** (NOT the drifted 16.51 — see §6); zone cap **18.89**; horizon **2026-08-31** (30 sessions). Operator has a **GTC buy-limit 18.89** resting; his one standing duty is the invalidation-cancel.
- **VSTS latch ARMED** — fire 2026-07-27; pivot **16.90**; stop 13.40; never_triggered (price ~15.58). Order standing above market.
- **Both are PRE-TELEMETRY latches** (`latch_view_events` created by migration 0032 on 07-28) — see §4.
- **A+ latch posture (adopted 2026-07-23):** an A+ fire LATCHES a GTC entry mandate at the fire's pivot plus a +3% zone cap; it clears ONLY on fill / setup invalidation / horizon; **bucket flicker never clears it**; a re-fire at the SAME pivot re-confirms, at a DIFFERENT pivot SUPERSEDES.

## 3. IN FLIGHT — and my gates

| Item | State | My gate |
|---|---|---|
| **H1 criteria amendment** | Commissioned; brief `docs/h1-criteria-amendment-commissioning-brief.md`; with CHARC for the architecture pass | Merge-blocking QA — **read the live registry row MYSELF post-migration** |
| **21-G** (provenance asymmetry) | EXECUTING in flight | Merge QA. **BINDING: 21-G merges BEFORE 21-B's ledger lands** |
| **21-B** (prepared-order form + execution-parity ledger) | writing-plans ~round 23; my two bucket rulings issued | Plan-stage review, then merge QA |
| **21-F** (dashboard latch surfacing) | Proposed; the order cache is a PREREQUISITE (CHARC forbade a broker call on the dashboard hot path) | The telemetry contract must settle BEFORE any dashboard surface ships |
| **21-C** (framework places/cancels orders) | Deferred behind stage-1 evidence + an operator-signed L2 endpoint diff | — |

## 4. RULINGS THE ARCS ARE BUILT ON — a fresh instance must not contradict these

- **Latch derivation:** freeze at fire time (read the FIRE's `candidates` row, never the latest — FTRE's pivot drifted 18.34 → 20.19 while armed); horizon in **NYSE sessions**, bound at the source to `cfg.pipeline.observe_max_pending_window_sessions`; per-FIRE identity with same-action-session duplicates collapsed; latch-specific fill detection; clear-reason recorded not inferred; invalidation on **closes**.
- **Zone escape is a STATE ATTRIBUTE, not a clear condition** (`LATCH_CLEAR_REASONS` = fill / invalidation / horizon / superseded only).
- **The stale-data asymmetry — applies to stale closes, cached order state AND run-level stamps: you may raise a MISMATCH ALARM but you may NEVER assert a MATCH.** Alarm permission is bounded to staleness that is **characterisable** (the price's date is PROVEN, not stamp-inferred) **and self-limiting** (the clock's fault, ending at the next run) — otherwise the alarm becomes the drumbeat class.
- **Three-state latch action:** accept / decline(+reason) / no-action. **No-action must NOT default to "away"** — split it by objective view-telemetry; **an unattested viewed-but-no-action defaults to DISCIPLINE LAPSE.** The instrument must not flatter its subject.
- **PRE_TELEMETRY is a distinct class**, not a flavour of away. Partial coverage: **a view record ESTABLISHES awareness; its absence over a partly-dark window establishes NOTHING.**
- **`pending_live` is excluded from every rate**; **`attested_was_away` gets its own bucket** — the away rate is reported **objective (gates the stage-3 decision)** vs **attested (an explicit upper bound)**.
- **Telemetry records WHICH LATCHES were rendered with actionable detail, plus the surface** — not merely that a surface was viewed.

## 5. RD-OWNED FOLLOW-UPS — with deadlines

- **THREE research-side instances of the run-level-stamp shape (gotcha #30) inside MY OWN measurement chain** — the 21-G survey hits 4, 5 and 7; consequences UNMEASURED; correctly flagged-not-fixed. **DEADLINE: read them BEFORE the August monthly read, because that read CONSUMES that chain.**
  - **First thing to check:** `evaluation_runs.data_asof_date` is **BAR-derived** (`swing/evaluation/orchestration.py:231`, cohort-max) while `pipeline_runs.data_asof_date` is **CLOCK-derived** (`swing/pipeline/runner.py:610`) — **two quantities under one column name**, agreeing 25/25 only because the nightlies are healthy. **My monitors read BOTH** (CALIBRATION C's whole-session-miss clause keys the clock-derived value; the detection/observation surfaces carry the bar-derived one). Registered **D27**; deliberately kept OUT of 21-G; scoped to the Phase-21 close or Phase 22. **Not asserted as a defect — not yet traced.**
- **MONTHLY READ #2 — due the first trading week of August**, with a real agenda: re-state T4 at n=312+ (Wilson LBs, unique-name counts, **the ETF split as a first-class cut**), test the survivorship-unwinding hypothesis, the three survey hits, T9 operationalization, the §3.2 log format. The catch-up read folds in here.
- **A+ spot-check cadence** continues to N=10 priced (currently 3: NVCR / AMN / FTRE).
- **Watch:** PGNY-class floor-boundary marks (the risk/ADR 0.15–0.2 band still amplifies — revisit only on REALIZED evidence); the day-3-vs-day-4 shadow-twin divergence (n=1).

## 6. BEHAVIOURAL — load-bearing, earned

- **Blunt over sycophantic; evidence before assertion** — every number freshly queried, never carried forward. Verify intent before labelling something a mistake, then be direct.
- **THE DOC IS A LEAD, THE CODE IS THE EVIDENCE.** I am reliable on SEMANTICS and unreliable on REMEMBERED CONSTANTS — **any figure a plan will build on must be TRACED at the moment it is stated.** Five instances this tenure: the pruner, the correction-chain grain, write-on-GET, the invented 20-session horizon that became its own citation, and a vacuous acceptance test I wrote.
- **SOURCE EVERY PREMISE FROM THE ROLE OR ARTIFACT THAT OWNS IT** — canonical in `harness-architecture.md` §2. A **fact** comes from code; a **position** from the role holding it, at POST time; **dispatch state** from the ORCHESTRATOR's last state statement; **gate state** from the gate-holder. If unclear, ASK — and NAME the statement being ruled against.
- **PRESERVE THE QUOTE** (§2, fifth row): a downstream editor corrects the surrounding text, never a director's quoted words — **the failure is invisible, because a softened quote still reads like a quote.** The director tightens their own words.
- **SUPERSEDES GOES IN THE SUBJECT** (§3) — a reader must tell from the inbox listing whether they are current.
- **GATE VISIBILITY** — the operator may authorize a merge over an outstanding director gate (his authority), but the merge report must SAY so in one clause. **A gate compressed because it would have passed anyway is advice with a ceremonial step.** Raised against my own gate.
- **NEVER MERGE CATEGORIES THAT DIFFER IN EVIDENCE KIND, even when their outcomes agree** (ruled three times). Outcomes coinciding is what makes merging tempting; reasons differing is why the design breaks. Keep softer measures as separate, explicitly-bounded forms.
- **A RULING IS PROVISIONAL ON ITS PREMISES** — a load-bearing number arriving later RE-OPENS it rather than being inherited by it.
- **Adjudicate residuals by DECOMPOSITION, never by prior plausibility** — D25: the $10 equity_delta instrument caught real corruption that both directors nearly dismissed as deposit drift.
- **Weight REALIZED (closed-only) over marks**; when primary scenarios disagree in sign, the pre-committed realized read binds.
- **QA the DIVERGENCE, never defend the brief — including my own rulings.** Twice this week a CHARC ruling beat my design by pricing a neighbouring step I had not traced; twice I reversed or withdrew my own position on the evidence.
- **Run `role_mail` with a `cd <main-repo> &&` prefix in the SAME command** — never trust a prior cd (2 misdelivery instances banked). Long bodies go via `--body-file`, never inline.
- Briefs crossing a CHARC §3 tripwire route through CHARC pre-dispatch. RD is merge-blocking on measurement integrity. **Default posture is STOP-ENGINEERING plus market time; deviations need written justification.**
