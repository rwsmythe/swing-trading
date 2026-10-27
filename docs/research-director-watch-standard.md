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

### §2.1 Execution procedure (added same-day 2026-06-10, operator-requested)

From the repo root:

```
python scripts/weekly_glance.py
```

Read-only (artifacts + `mode=ro` DB); ~5 seconds. It prints the last ~7 nightly runs (detections / signals /
unattributed / trigger rate), the newest-artifact age, this week's live entries with their intent labels, and any
risk/reconciliation or `CHASED`/`NO_SETUP` tags on `standard`-intent trades — then either `WEEKLY GLANCE: all clear`
or `ATTENTION` lines pre-mapped to the §4 tripwire IDs (T1/T2/T3/T6/T7). T2 fires on the NEWEST run only (older
artifacts may legitimately predate a registry amendment — e.g. the pre-0026 runs honestly show 42/42 unattributed
forever; they are history, not a regression). Any `ATTENTION` line → message the research director with the output;
do not wait for the monthly read. `T7 check` lines on `by_design` entries are self-checks (legitimate only for
H2/H4 program fires).

The manual fallback (if the script is unavailable) remains:

1. The newest `exports/research/shadow-expectancy-*/summary.md` is from the last trading session (drumbeat alive).
2. In it: `total_unattributed = 0` (nonzero on the NEWEST run → §4 T2).
3. `unique_signals` is moving across the week (the log is accruing).
4. Trigger rate numerator: still `0/N`, or has the FIRST breakout priced? (nonzero → §4 T3 — good news, but gated.)
5. If any live trade was entered this week: it carries the intent label per the epoch contract (charter §7) and no
   risk/reconciliation tag landed on a `standard` trade (else → §4 T6).

### §2.2 T3 status note (2026-06-10)

The first-priced-trade golden gate is **DONE** — run `20260611T041306Z` priced the first 5 signals (2 unique names);
the research director hand-walked BOTH names against raw forward bars (WULF: entry 27.47 / stop 24.095 / stop-out
−1.0000R `initial_stop`; VECO: entry 65.03 / stop 61.86 / +0.2871R `horizon_mtm`) — exact match on fills, stops,
R-arithmetic, and the `entry_bar_weak_close` diagnostics (charter §7, 2026-06-10). Per §4 T3, the remaining
obligation is spot-checking ~1-in-5 NEW priced trades until N=10, then trust the machinery.

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
   censoring scenario, **priced N vs the broad-watch N≥30 decision gate** — tracked at BOTH the signal level (the
   spec's unit) **and the unique-name level** (re-detections of the same name across runs walk identical bars →
   identical R → correlated samples; the first priced batch was 5 signals / 2 names). The T4 decision read must
   report both counts. First priced trade → §4 T3 if not yet done.
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
- Pricing: trigger <k>/<n>; priced N=<n> signals / <m> unique names (gate 30); scenarios <closed_only n / mtm n / forced n / adverse n>.
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

---

## Version 2 — 2026-06-16 (research-health monitor integration)

**RD-authored 2026-06-16; operator-acknowledged 2026-06-16 — ADOPTED.** SUPPLEMENTS v1 (the §1 cadence + §4 tripwires + §5 decision points stand unchanged); adds the MECHANIZED data-integrity surface that v1's §2/§3 prescribed in prose. Motivated by + closes the 2026-06-13 RD data-collection audit (the temporal-log NaN defect rode invisible 2+ days because the operator-facing surfaces watched the funnel/intent layer, NOT the data-integrity layer).

**What shipped (Phase 18 audit chain, now fully closed + automated):** `swing/monitoring/research_health.py` (`compute_research_health`) + the operator/RD probe `scripts/research_health.py` + a nightly pipeline step refreshing `exports/research/health/latest.json` every pipeline run + the 18-F GUI research stoplight that reads it. Chain: 18-A writer fix → 18-B consolidation → 18-C yfinance observability → 18-D monitor + FIX-1 baseline + 18-B.1 structural prevention → the nightly half + 2 calibrations.

### §2 supplement (weekly glance)
The operator runs `PYTHONPATH=. python scripts/research_health.py [--json]` **alongside** `weekly_glance.py`. weekly_glance watches the funnel/trigger/intent layer; the monitor watches the **data-integrity** layer (the 7 checks below). The 18-F research stoplight is the passive glance surface (green/yellow/red, refreshed nightly). Any monitor **RED** → message the RD (same as a glance `ATTENTION`). (The `role_mail`-on-ATTENTION auto-push to the RD inbox is **18-H.7-deferred** — until then the stoplight + the operator's glance ARE the surface.)

### §3.1 supplement (monthly read)
The monitor MECHANIZES the data-integrity dimension. The 7 checks: **#1** temporal_log_finiteness · **#2** excluded_reason_breakdown · **#3** coverage_gaps · **#4** structural_integrity (orphans/look-ahead) · **#5** drumbeat_liveness · **#6** candidate_completeness · **#7** fetch_transport_health (yfinance_calls TRANSPORT indicator only — best-effort; `success` ≠ data usability; **#1 is the usability authority**, never substitute #7 for it). The monthly read RUNS the monitor + reads its checks — STILL cross-checked against the live DB per the §3 fresh-query evidence discipline (the monitor is a surface, not a substitute for the fresh-query rule).

### >>> CALIBRATION SEMANTICS — a future RD MUST read the monitor through these or misread accepted history as a failure:
- **#1 GREEN ≠ zero non-finite.** It means zero POST-BASELINE non-finite. The **103 obs @ ≤2026-06-13** (the 06-10 cohort) are the ACCEPTED-historical, withdrawn-backfill set (immutable log; FIX-1 cutoff `_FINITENESS_BASELINE_CUTOFF=date(2026,6,13)` = the 18-A writer-fix boundary) — surfaced in the check DETAIL ("accepted historical: 103 …"), NOT a failure. **A #1 RED = a NEW non-finite (observation_date > 2026-06-13) = a write-barrier REGRESSION** (18-A/18-B/18-B.1 make this impossible by construction — the `insert_observation` guard) → **IMMEDIATE T2-class investigation** (the structural-prevention guarantee broke). A CORRUPT/unparseable obs json is ALWAYS red regardless of date.
- **#2 invalid_ohlc is judged as a RATE of unique signals (D82, merged 2026-10-20 `29679b05`; RD F5):** green iff `count * 20 <= unique_signals` (≤ 5.00%), red iff `count * 10 > unique_signals` (> 10.00%), yellow between — INTEGER cross-multiplication (`_INVALID_OHLC_GREEN_DIVISOR` / `_INVALID_OHLC_RED_DIVISOR`), never the rounded display; detail reads `invalid_ohlc=<n> (<x.xx>%, <band>; yellow above 5.00%, red above 10.00%)`. **The count baseline of 23 (CALIBRATION B) is RETIRED** — it had sat at its yellow floor since 2026-09-24 (71 > 23 with no mechanism to escalate: a dead light). At 1,535 signals: green ≤ 76, yellow 77–153, red ≥ 154; live 71/1535 = 4.63% GREEN. The counted set includes OHLC INCONSISTENCY, not only non-finite values (validate.py), which is why 23 grew to 71. `insufficient_forward_depth` + `missing_observations` are **NOT** baselined (different causes — log-maturity / attribution; they self-heal as the log accrues). **As of the 2026-06-16 first nightly run the overall is honest YELLOW driven by `missing_observations` (~16.3%)** — a self-healing maturity signal, NOT the 06-10 cohort; do NOT relabel it a defect.
- **#3 coverage_gaps = CALIBRATION A (trailing-1 grace) + CALIBRATION C (current-vs-historical, shipped 2026-06-25; trailing-delisting widening 19-A, merged 2026-07-03 `fadc193d`).** Tolerates a TRAILING ≤1-session lag (`_COVERAGE_TRAILING_GRACE_SESSIONS=1` — the newest completed session not-yet-observed pre-nightly). **CALIBRATION C accept rule (post-19-A): a session is accepted iff `skip_explained` OR (`clause1` AND `whole_session_miss`)** — the two clauses are now asymmetric by design: **(2b) skip-explained** — a per-(ticker, session) `pattern_observe` skip-warning (`no bar for observation_date` / `non_finite_ohlc`) is DIRECT evidence of a benign no-bar and is accepted whether the hole is interior, leading, **or TRAILING/never-observed** (the 19-A fix: a DELISTED/acquired ticker's holes are trailing — the CNTA 07-02 false-RED class; clause-1 no longer gates 2b); **(2a) whole-session missed run** (no completed `pipeline_runs.data_asof_date` row for that session) stays clause-1-gated — accepted ONLY when the drumbeat provably moved PAST the hole (a later session for that detection IS observed). **Consequence-#2 semantics (RD-blessed 2026-07-03, two bounds):** a NEVER-observed detection whose expected sessions are ALL skip-explained is accepted (immediate-delisting-after-detection — unobservable by construction); the bless attaches to (i) the CURRENT `_observe_skip_index` admission rule (`state='complete'` run + the 2-reason allowlist + `observation_date == data_asof_date`) — any loosening RE-OPENS the review — and (ii) the `N accepted historical` summary/detail surfacing staying intact (mass-acceptance VISIBILITY is the compensating control for trusting skip-warnings; #7 remains the transport alarm). **Still reds (unchanged):** a trailing lag ≥2 with NO skip-warnings (drumbeat behind/dead — a real outage emits none), an UNEXPLAINED interior hole, a zero-observation observe FAILURE (run named the session, wrote nothing, no skip-warning), a globally-observed-but-no-ledger hole, and partial explanation (unexplained sessions stay counted per-session). A degraded/unparseable run-ledger date → clause-2a conservatively DISABLED; an unparseable warning is DROPPED from the skip index (both degrade toward red; never accept-everything). History: the 2026-06-24 missed-06-22 RED reads `842 accepted historical`; the 2026-07-02 CNTA delisting RED (100 gaps) reads accepted post-19-A (live-verified GREEN, 947 accepted).

### Cadence + tripwire tie-in
The nightly step refreshes `latest.json` every pipeline run; the 18-F staleness gate greys it if >7d stale (= a drumbeat-dead **T1** signal at the GUI). A **#1 RED** (post-baseline non-finite = a write-barrier regression) is a **T2-class HIGH** (substrate-integrity break) → same-session investigation; the structural prevention means it should never fire, so if it does, a barrier regressed.

---

## Version 2.1 — 2026-07-07 (evidence-artifact tracking: the cite=commit read discipline)

**RD-authored 2026-07-07 at the Phase-19 close (the Option-C convention, thread `shadow-expectancy-track-vs-ignore`); operator-acknowledged in-session.** SUPPLEMENTS v2; nothing else changes.

- **§3 read-discipline addition:** a decision-read / study / golden-gate verification that CITES a shadow-expectancy engine artifact **COPIES the cited ledger files** (`summary.md` / `manifest.json` / `results.csv` / `per_session.csv`) **into the citing study's tracked location** (`research/studies/<study-slug>/artifacts/<artifact-ts>/`) **and commits them with the read.** Rationale: `exports/research/shadow-expectancy-*/` is fully EPHEMERAL (gitignored + keep-90 pruned since `0d560822`) — cited = committed = prune-proof; an uncommitted citation is evidence with a ~2-month fuse.
- **Contract enforcement:** `tests/research/shadow_expectancy/test_study_doc.py::test_cited_artifacts_are_git_tracked` asserts the cited set is git-tracked (the REAL contract; the old allowlist assertion was aspirational — zero artifacts had ever been committed).
- **Location convention:** an artifact cited by a non-study doc (e.g. the §2.2 T3 golden gate, cited by THIS standard) lives in the artifacts dir of the study whose program it evidences (the T4 study dir) rather than a bespoke location — RD location-call 2026-07-07.

## Version 2.2 — 2026-09-02 (the maturity gate + two read disciplines; owed by read #2, paid before read #3; OPERATOR-ACKNOWLEDGED 2026-09-02 per §6.5)

### §3/§5 supplement — THE T4-CLASS MATURITY GATE (binding on every decision read)

A decision read (T4, H1, H2, H4, or any §5 gate) **may not BANK a verdict from a cohort below
maturity.** The August withdrawal is the evidence: a FIXED cohort's closed-only mean moved
−1.00 → +0.21 purely by aging, because losers resolve in days at `initial_stop` while winners
trail out over weeks via `ma_close_below` — a young cohort's closed set measures RESOLUTION
SPEED, not edge, and maturity dominated the estimate by ~1.2R.

Operationalization (the curve/bracket instrument, `research/studies/2026-08-01-t4-maturity-withdrawal/`):

1. The read reports the **age-bracket table** (closed-only mean R by minimum cohort age in NYSE
   sessions) and, where a longitudinal artifact series exists, the **fixed-cohort maturity curve**.
2. The decision number is the bracket at or past the **winner-resolution window** — re-derived
   per ruleset from the exit-mix columns (the age at which `ma_close_below`-class exits reach
   steady share), never inherited as a constant. On the current operational ruleset the evidence
   says ≈30 NYSE sessions.
3. **BANKING requires BOTH:** (i) cohort age past the winner-resolution window, AND (ii) the
   decision bracket's confidence width smaller than its distance to the decision boundary.
   Below either: the verdict is **UNDETERMINED — trajectory reported, nothing banked.**
4. This amends the READ, not the registry: the frozen criteria are untouched (§5 — a watch read
   never adjusts a criterion). What changes is what a read may CLAIM from an immature cohort,
   exactly as the 2026-08-01 withdrawal practiced.

### §3 supplement — THE ARMING-READ DISCIPLINE (item-3 lower bound, generalized)

Any read that decides to **ARM a rule** from a report-only instrument observes this asymmetry:
report-only would-fire counts are a **LOWER BOUND on armed churn** (topology change under-counts,
biasing TOWARD arming). A safe-looking bound is therefore **NOT sufficient to arm** — corroborate
on the topology-stable subset first. A costly-looking bound **IS sufficient not to arm.** The
asymmetry is the rule; citing the bare would-fire count as arming evidence is the violation.

### §3 supplement — LAPSED LIVE-VS-SHADOW DIVERGENCE IS THE RULE'S MEASURED VALUE (OQ-3)

Once `criteria_lapsed` (or any live-only lifecycle rung) arms, live-vs-shadow divergence on the
affected cohort is the EXPECTED product of the rule operating — the shadow does not lapse, the
live does, and **the divergence IS the rule's measured value.** A future read reports it as the
rule's effect, never as a parity anomaly to reconcile away. Standing corollary (ruled 2026-08-25,
binding from read #3 onward): the shadow A+ arm's stop geometry (entry-bar-low) differs from the
live mandate doctrine (frozen candidate stop) BY DESIGN — the arm's mean measures ITS OWN
geometry, and any report of that mean carries the caveat plus the live-vs-shadow pair table.

## Version 2.3 — 2026-10-20 (the D90 observe-ladder detach: a V2.1 §VII.F boundary note + read caveat (d) on `$.provider`)

**RD-authored 2026-10-20 at the D90 merge (`baac5c20`, tree `bb26970b`; both director gates cleared at `c0c92de7`, released after run 196). SUPPLEMENTS v2.2; nothing else changes.** Owed by the D90 F1 ruling (branch A, detach always; RD 20261020T072525Z) and the merge clearance (RD 20261020T092235Z).

### §VII.F BOUNDARY NOTE — D90
- **What changed:** from the merge, `_step_pattern_observe`'s archive populate passes `use_ladder=False` and never reaches the Schwab market-data ladder (`swing/pipeline/runner.py:_bar_for_date`; `swing/web/ohlcv_cache.py:get_or_fetch`). Observe makes no Schwab call and writes no `schwab_api` archive row. Detect's ladder call and the web process's hook are unchanged.
- **Boundary:** the first post-detach nightly is `pipeline_runs.id` **197** (data_asof 2026-10-21; CONFIRMED 2026-10-21 by RD on the live DB mode=ro: run 197 complete 17:30:04–17:33:14 HST; observe 42,758 ms; Schwab price-history calls inside observe's window with `surface='pipeline' AND pipeline_run_id=197` = 0 against 33 outside it; provider mix yfinance 6,835 / schwab_api 0; `resolve_reads` 247). Run **196** (2026-10-20, observe 142,234 ms, 241 Schwab price-history calls inside observe, provider mix yfinance 6,919 / schwab_api 0) is the last pre-detach run and the baseline for the D90 witness; run 195 is NOT (it predates D89).
- **Measurement consequence (RD, neutral by the two-pair N-V, `tests/pipeline/test_observe_ladder_detach_neutrality.py`):** on an ordinary night the observation rows are byte-equal with and without the detach. On a CARRY night (observe running while `observation_date <= Schwab's previous business day`: a hand-launched post-midnight-ET run, or a holiday-evening run such as Thanksgiving evening 2026-11-26) an OBSERVE-ONLY ticker's row now carries `$.provider = yfinance` where it would have carried `schwab_api`; values are equal (newest-bar divergence p99 0.06%, the 12 carry dates p99 0.00%). A DETECT-POOL ticker's row may still carry `schwab_api` on a carry night, because detect's own ladder call wrote that date's row minutes earlier in the same run. **The provider on an observation row is a LABEL, not a value regime.**
- **Pre-boundary rows:** 9,474 of 337,582 observation rows (2.8%) carry `schwab_api`, on 12 carry dates (eleven in June 2026 from the hand-launched post-midnight runs 90–116, plus 2026-09-04 from the Labor-Day-evening run 170). They need nothing and are not rewritten (immutable log).

### §3 read caveat (d) — `$.provider` MIXING
Any read that conditions on, filters by, or groups by `ohlc_today_json.$.provider` states this caveat: the label mixes two mechanisms (the 12 historical carry dates; future carry nights, now detect-pool tickers only) and does NOT partition the rows by value quality. On an ordinary night "all yfinance" is TRUE BEFORE AND AFTER the detach (run 196 read it pre-detach with the ladder on), so it discriminates nothing about D90; the discriminating post-merge reads are W1 (ZERO `schwab_api_calls` with `surface='pipeline' AND pipeline_run_id=<run>` inside observe's step window, against 241 on run 196) and the observe wall against 142,234 ms. A provider-conditioned analysis of the ARCHIVE exists (orchestrator scan 2026-10-20: 4,914 of 276,350 shared rows diverge > 1% on 55 tickers; CRWD's Schwab close is one quarter of yfinance's, LILAK's 47% above; opposite signs, mechanism unread) and is registered as **D92** (range reads merge two adjustment bases; owner RD on semantics, CHARC on form, after D84). Observation rows are unaffected by D92 (observe selects the observation-date row only; the log holds zero zero-priced rows). The uniform-source alternative stays banked (owner RD; trigger: carry-date divergence > 0.5% on > 1% of pairs, or a provider-conditioned analysis of OBSERVATION rows).

## Version 2.4 — 2026-10-27 (the D84 capital soft-stop: a V2.1 §VII.F boundary note + the era-keyed re-use precondition + read caveat (e) on `decision_r_attested`)

**RD-authored 2026-10-27 (2026-10-26 evening HST) at the D84 merge (`42d0365c`, `--no-ff` of `d84-exec` tip `1ab9d871`; the nine research era pins filled docs-only at `54c5a299`; the operator's plan 6.3 witness recorded at `6994d32c`, every step PASS). Both director gates cleared at `5f64a1be` (RD executing-return gate `20261026T201443Z` + addendum `20261026T201519Z`; CHARC merge gate `20261026T201425Z`); CHARC called MAIN GREEN `20261026T222645Z` on 15,624 passed / 13 skipped / 0 failed. SUPPLEMENTS v2.3; nothing else changes.** Owed by the D84 plan-stage read (RD clearance at plan tip `6137a7b6`, item B ruled) and the O-1 ruling (ledger `1d7c2580`).

### §VII.F BOUNDARY NOTE — D84
- **What changed:** from the merge, `risk_feasibility` is a FLAG, not a gate. `bucket_for` no longer pre-skips a risk-fail name; the bucket is structural. The cohort rule moved with it: **H1 = `aplus` AND the risk layer PASSES; H4 = `aplus` AND the risk layer is FLAGGED; an EMPTY risk layer is NEITHER** (`swing/evaluation/scoring.py`: `risk_layer_passes` requires `risk_result_count >= 1`; `risk_layer_flagged` requires `risk_non_pass_count >= 1`). The pre-boundary H4 form (`watch`/`skip` with risk the only miss) was DROPPED from the matcher; it never matched a persisted row (0 exact-`{risk}` rows among 312 risk non-pass rows, runs 1–180, q6), so no history re-attributes. The derivation rule is a REAL change: `DERIVATION_RULE_HISTORY` gained `("2026-10-26.1", 30ac9063…)` (the one-line date fill at `1ab9d871`; the digest hashes the manifest only and did not move). The two live `provenance_corrections` rows keep `2026-08-26.2`; the next row carries `2026-10-26.1`. No migration; schema stays v41.
- **Boundary:** the first post-boundary nightly is `pipeline_runs.id` **200** / `evaluation_runs.id` **186** (data_asof 2026-10-26; CONFIRMED 2026-10-26 by RD on the live DB mode=ro: started 17:30:11, complete 17:33:37 HST, on main at or after `54c5a299`; 39 tickers, risk 39/39 pass, `aplus` 0 / `watch` 12 / `skip` 27). It carries ZERO risk-flagged rows, so **the boundary is quiet by observation: no `RISK FLAG` marker, no H4-eligible card, no step in the persisted counts yet.** The last pre-boundary run is **199 / 185** (2026-10-23; 36/36 risk pass; 0 / 13 / 23 / 1 excluded). Friday 2026-10-24 has no run (the task did not fire; one missed session, cause unconfirmed, not T1). `swing web` on 8080 was restarted on the merged code 17:33 HST (pid start time read). The live DB is untouched by the witness (28 trades, 14 intents, no seeded ticker; the witness ran on backup-API copies).
- **History unchanged (q6 re-run POST-merge, 2026-10-26):** 19 of 19 persisted `aplus` rows (runs 9…153) carry a `risk_feasibility` PASS row; 0 lack a risk row. So every pre-boundary `aplus` row is H1 under the new conjunct, the H1 cohort's history is byte-identical, and H4's delta on history is 0. **No `hypothesis_status_history` row was written** (plan ruling S2 = (a); the table holds its 8 rows, last 2026-06-10): the boundary's homes are the derivation-rule version string above and THIS note. The registry's five rows keep their n and criteria.
- **The marker IS the label.** On every surface (latch card, dashboard near-trigger rows, `/watchlist` and its expansion, the briefing) the risk flag renders as the ASCII marker `RISK FLAG` with no sizing number; a card's lead paragraph is CONDITIONAL on card state (determinable rung = "RISK FLAG - 0 SHARES AT THE BUDGET" with the stated zero; band card = "PREPARED ORDER WITHHELD" + the stated zero + the D84 affordance and NO marker, because its risk layer PASSES; control = `BUY n` with ACCEPT/DECLINE). A fill on a risk-flagged A+ prefills **`Capital-blocked: smaller-position test (aplus); failed: risk_feasibility`** and never the H1 label (R-T4.5 / R-T4.6; witness step 3). The marker renders for ANY bucket whose risk layer is flagged, so a risk-fail WATCH name is not silent.
- **H4 is an OPERATOR-ASSERTED cohort (declared limitation, plan 0.3; register D96).** Every H4 fill is operator-typed text with no `AcceptedLatchOrder`, so tier-2 provenance cannot reach it. A mislabel's remedy is the Demand-C correction surface (reachable from the boundary; R-T4.6). Re-open trigger: F1-B or D94 (c). **Amendment 3 is DISCHARGED** (CHARC `20261027T033628Z`): the stub built the production `EntryAutoFillResult(kind="populated")` and replaced ONLY the Trader call, so every line from the resolver's return to the rendered input was production code (7 shares beside the stated zero, operator paste). What it cannot prove is the resolver's REAL return on a flagged ticker (the synthetic-fixture-vs-production-emitter class); that is a WATCH, closed at the first real auto-filled entry on a flagged ticker, and it is my witness item below.
- **The watch pool widened too.** Removing the pre-skip routes a risk-fail name with a structural near-miss into `watch`, not only passes into `aplus`. Cell 2's F3 simulation over every persisted criteria row (`bucket_for` reproduces 14,787 of 14,789 persisted buckets): **30 rows / 12 tickers, all in runs 1–112, would newly have qualified**; none is rewritten (immutable). H2's exact-set matcher excludes risk-fail by construction; H5 (broad-watch) gains risk-fail near-misses FORWARD only. The per-run persisted `aplus_count` / `watch_count` / `skip_count` STEP at the boundary when a flagged name next appears (CHARC A1; no reader gates on them). The series 183–186 reads 0/8/24, 0/10/28, 0/13/23, 0/12/27: no step yet.
- **"aplus-origin" now means STRUCTURALLY A+** (`swing/evaluation/pe_origin.py` `PROVABLE_APLUS_PE_PREDICATE`, item B1): from the boundary the pattern-outcome cohorts, the active-learning queue and the review-form cohort admit risk-flagged A+ names and no longer imply "sizable at the floor". History unchanged; no test (the risk layer never reaches the predicate). The T9 pattern reads compare across the boundary only with this stated.
- **The Finviz widening is NOT in D84.** It is the operator's config edit the night after (proposal §4, stage 1) and gets its OWN dated note (v2.5: the three filter changes, the first widened `finviz_api_calls.call_id` + `signature_hash`, the first widened run ids). The proposal's two "five `hypothesis_status_history` rows" sentences are SUPERSEDED by S2 = (a) above and were replaced in the proposal the same day.

### §4 precondition — THE ERA-KEYED RE-USE RULE FOR THE DORMANT RESEARCH HARNESSES (binding; adds to the v2.2 "hits 4/5" precondition)
A comparison that crosses the D84 boundary is **era-keyed on the persisted row's evaluation run date, in BOTH directions**, before any number from it is quoted:
1. **Mirror direction (the nine pins):** the research mirrors of `bucket_for` (`aplus_sensitivity/sweep.py` `_bucket_for_substituted`; `aplus_v2_ohlcv_evaluator`; `minervini_exemplar_recall/screen_eval.py`; `earnings_proximity/recompute_binding_prod_gated.py`; `finviz_pool_analysis/aggregator.py`) are pinned to the PRE-D84 gate (risk hard filter retained) and read a post-boundary risk-flagged A+ as a divergence from production. **Re-align before any re-use.**
2. **Reverse direction (O-1):** a PRE-boundary row whose risk failed was persisted `skip` by the pre-skip; CURRENT `evaluate_one` recomputes it to its structural bucket, so the mismatch is an era divergence BY CONSTRUCTION, never a surrogate condition and never a parity failure (`context_builder.py` `classify_candidate_tier`, the O-1 clause). The V2 tier-2 lane fills with era divergence from the boundary; tier 1 is unaffected.
3. **The four harnesses and their mechanism:** (a) `aplus_v2_ohlcv_evaluator` — tier 2 over-assigned post-boundary, era-divergent pre-boundary; (b) `research/parity` (closed H5) — one `evaluation_run_id` per comparison, so a pre-boundary run id now disagrees on its risk-fail rows; (c) `minervini_exemplar_recall` — the H1 bucket follows current `evaluate_one` (structural) while `first_rejecting_gate` follows the pre-D84 mirror, so the two no longer agree on a risk-fail name by design; (d) the `earnings_proximity` diagnostic — its capital-multiplier probe of the operator hypothesis "low capital binds `risk_feasibility`" is UNREACHABLE under post-D84 production (risk never binds the bucket); re-run it against the pre-D84 mirror, or restate the hypothesis as the risk FLAG's incidence against capital (post-boundary rows carry the persisted risk row), never as bucket binding.
4. **The aggregator's drift WARNING fires BY DESIGN** on a post-boundary risk-flagged A+ (`aggregator.py` `consistency_warnings`: "bucket=aplus but pre-D84 mirror blocker=risk_feasibility … expected for a post-D84 risk-flagged A+"). It is the era divergence surfacing, not a defect; a read that counts those warnings as failures is wrong.

### §3 read caveat (e) — `decision_r_attested` MIXES TWO CARD KINDS
From the boundary the parity ledger's `decision_r_attested` (`swing/latches/classification.py`) holds BOTH H4 attestations (risk-FAIL cards: `acted_manually` + broker order id, witness step 2) AND band-card attestations (risk PASSES; limit-basis sizing is zero; CHARC amendment 1, witness step 6). **Partition by the fire candidate's persisted risk layer at read time, never by the bucket** (both are `aplus`). A declaration on a LIVE card now reaches the correction affordance with all three answers (W-1, registered **D99**, a `swing/web` rider, CHARC `20261027T033628Z`): until it lands, a mid-window `was_away` on an armed card is testimony about a window that had not closed and scores at terminal as attested-away, so a read of `attested_away_r` partitions ARMED-at-attest rows from terminal ones.

### RD reads owed on this boundary (standing, until each is paid)
- **The first risk-flagged A+ that fires:** read its card against the ruled marker and lead paragraph for its state, its fill's prefilled H4 label and the limitation text, and the ledger row's attestation kind, BEFORE any other read quotes it. If it is auto-filled, it also closes amendment 3's live-emitter watch (record in the exec ledger; report to CHARC).
- **The November read (#5):** `degenerate_risk` and `invalid_ohlc` on both sides of the boundary; the count series step, if any; every number era-keyed per §4 above.
- **The Finviz widening's own note (v2.5)** the day the operator makes the config edit.
