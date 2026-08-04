# The `data_asof_date` consumer survey (Arc 21-G)

**Commissioned by:** the 21-G brief §2.4 (`docs/archive/phase21/provenance-asymmetry-21g-commissioning-brief.md`). **Performed:** 2026-07-28, at writing-plans, against main `1955aa59` (schema v32) and the live DB + prices cache, read-only. **Duplicated verbatim as §S of** [`docs/superpowers/plans/2026-07-28-phase21-arc-g-provenance-asymmetry.md`](superpowers/plans/2026-07-28-phase21-arc-g-provenance-asymmetry.md) so the plan is self-contained; this file exists because a plan is archived after execution and a director needs a stable thing to cite.

**RD's epistemic position, preserved verbatim and load-bearing:** *"I am not asserting it is a class — I am refusing to assume it is not."*

**This survey REPORTS. It does not authorize fixing any hit.** Everything below except hits 1 and 3 comes back for scoping — **hit 3 was FOLDED IN by RD on 2026-07-28** and is now an in-scope 21-G task. The shape being surveyed is cumulative gotcha **#30**: *a run/batch-level stamp is not provenance for a per-row value.*

**Hits 4, 5 and 7 are RD-OWNED WITH A DEADLINE (2026-07-28): he will read them before the August monthly read, because that read consumes the chain they sit in.** They are stated at the strength the evidence supports and no weaker; a future edit may correct them but may not soften them.

---

## 0. The headline for a research reader: TWO QUANTITIES SHARE ONE COLUMN NAME

Before any individual hit, the structural fact RD called **the most consequential item in the arc for his lane**:

| column | derivation | computed |
|---|---|---|
| `evaluation_runs.data_asof_date` | **BAR-derived** — `max()` over per-ticker last bar dates | AFTER the fetch (`orchestration.py:229-231`) |
| `pipeline_runs.data_asof_date` | **CLOCK-derived** — `last_completed_session(run_now)` | BEFORE any bar is fetched (`runner.py:610`) |

They agreed in **113 of 113 paired runs across the full history** (RD, measured 2026-07-28 on the live DB), including **17 runs started during US market hours** — precisely where a partial-bar divergence would surface. **The agreement is STRUCTURAL in one direction and unenforced in the other, and RD corrected his own first statement of this (2026-07-29) — use this form:** both bar consumers cap at the clock session as read at **FETCH** time (`PriceFetcher.get` slices `<= _resolve_asof(None)`, `swing/prices.py:56-68`; the detector's separate source `OhlcvCache.get_or_fetch` strips bars `> end`, `swing/web/ohlcv_cache.py:293-310`), while the persisted `pipeline_runs` stamp read the clock at **LEASE** time. So bar-derived can never exceed the clock session *as read at fetch time*, and can exceed the **persisted** stamp only if the run **STRADDLES a session close** between lease acquisition and fetch. **That is not a second hazard — it is the SAME event as hit 7's look-ahead path, measured 0 of 140 completed runs.** D27's agreement and hit 7's safety therefore rest on ONE sufficient condition, not two. The reason to fix the naming is unchanged: a reader cannot tell which quantity they are holding. RD's framing, preserved verbatim:

> *"worse than a latent hazard — a hazard that LOOKS CORRECT. A reader who conflates them is not being careless; the schema is telling them the two are the same thing."* — **tightened by RD himself 2026-07-29** after the fold-in review caught the original clause claiming more than the evidence supports, per the preserve-the-quote convention (the director tightens it, not a downstream editor):
>
> *"Archive lag is ONE condition under which the two quantities diverge, and it is the one that matters for Route B — but it is not the only one, since the `as_of_date` and `last_completed_session` branches can diverge for unrelated reasons. The correct claim is that the collision and the Route-B hazard CAN fire together, not that they always do."*
>
> **What survives the correction unchanged, and is why the finding still matters (RD):** *"A reader cannot tell which quantity they are holding."* That is true regardless of how often the two diverge, and it is what makes the naming defect worth fixing on its own merits rather than as a rider to the divergence frequency.

**An archive lag — the Route-B condition — is exactly the kind of thing that makes these two columns disagree, and the schema will not warn anyone when they do.** Any reader of hits 4, 5 or 7 should read this section first: those consumers each pick ONE of these two columns, and WHICH one they picked is part of what makes them a hit.

**What the measurement does and does not establish (Codex R8 MINOR — the honesty lock applied to RD's own framing, which is preserved verbatim above rather than softened).** The 25/25 agreement is an OBSERVED coincidence across sampled HEALTHY paired runs. It establishes that the two columns are computed independently and that nothing enforces their agreement. It does NOT establish that the FIRST divergence will coincide with a Route-B lag: the `as_of_date` and `last_completed_session(run_now)` branches (`orchestration.py:232-235`) can diverge from the clock-derived stamp for reasons that have nothing to do with per-ticker provenance. So read the coupling as *the archive lagging is one way — and the one this arc cares about — to make these two columns disagree*, not as a proof that a disagreement implies a lag or vice versa. The reason to fix the naming is that a reader cannot tell WHICH quantity they are holding, which is true regardless of how the two first diverge.

---

## 1. Method

1. `grep -rn "data_asof" --include=*.py --include=*.sql --include=*.j2 swing/ research/ scripts/` (tests excluded from the consumer census; they are not consumers).
2. Every `evaluation_runs` reader enumerated by `grep -rn "evaluation_runs"` and each JOIN site read in full.
3. Every `data_asof_date=` **write** site enumerated, to trace where a run-level stamp is COPIED onto per-row tables.
4. Each hit classified against the #30 trigger: *does this consumer treat a run/batch-level stamp as provenance for a per-ROW value?*
5. Each claim checked against the live DB / live archive (read-only), not against the code comments.

## 2. There are FOUR distinct `data_asof_date` columns with TWO different semantics

| column | written by | semantics |
|---|---|---|
| `evaluation_runs.data_asof_date` | `swing/evaluation/orchestration.py:229-235` | **DATA-derived**: `max()` over per-ticker last bar dates (branch 1), or a CLI `as_of_date` (branch 2), or `last_completed_session(run_now)` (branch 3) |
| `pipeline_runs.data_asof_date` | `swing/pipeline/runner.py:610` -> `swing/pipeline/lease.py:271` | **CLOCK-derived**: `last_completed_session(run_now)`, computed BEFORE any bar is fetched |
| `daily_recommendations.data_asof_date` | `swing/recommendations/build.py:54,83` | a COPY of the evaluation-run stamp onto PER-TICKER rows |
| `pattern_detection_events.data_asof_date` | `swing/pipeline/runner.py:2834` (via `lease_data_asof`) | a COPY of the CLOCK-derived pipeline stamp onto PER-TICKER detection rows |

Plus `chart_renders.data_asof_date` (per-ticker chart rows, migration 0020) and `watchlist.last_data_asof_date` (per-ticker streak key, `swing/watchlist/service.py:108-183`), both copies of a run-level value onto per-row records.

**Two different quantities share one name.** Empirically they have never diverged: **113 of 113 paired runs across the full history** (RD, 2026-07-28, live DB), including 17 started during market hours. The agreement is **structural in one direction** — both bar consumers cap at the fetch-time clock session — and unenforced in the other; the only way bar-derived can exceed the **persisted** stamp is a run that straddles a session close between lease acquisition and fetch, which is the same event as hit 7's look-ahead path and was measured at **0 of 140**.

## 3. Empirical incidence of the underlying gap

Measured read-only on 2026-07-28:

- Across the last **12** evaluation runs, per-ticker `candidates.close` values were matched against dated Shape-A archive bars: **zero** tickers were observed carrying a close older than their run stamp. (The single apparent hit, `PK` matching a 2023 bar, is a price coincidence, not a lag.)
- For evaluation run 127 (`data_asof_date = 2026-07-27`), of the 60 candidate rows with a close, **31 of the 31 that have a Shape-A archive matched their 2026-07-27 bar to the cent**; the other 29 have no Shape-A archive at all (the legacy-only `{TICKER}.parquet` population).

**So the run-level-stamp route is a LATENT STRUCTURAL hazard, not an observed defect.** The write path guarantees nothing about the coupling, so the absence of a lag today is luck rather than an invariant — but no reader of this survey should cite a frequency it does not have.

## 4. The hits

**Hit 1 — `swing/latches/reader.py:258` + `swing/web/view_models/latches.py:860` (the latch mandate-FORM check).** The `(close, stamp)` pair is read together and the stamp gated a form ASSERTION: `last_close = quote[0] if quote[1] == regime_session_iso else None`. A ticker whose archive lagged the cohort passes that gate with an older close and gets an order form blessed off a price the market had left — a false ALL-CLEAR. **FIXED in 21-G** (the close-provenance ladder: assert only from a close corroborated at the derivation session, alarm only from one corroborated at its own stamp).

**Hit 2 — `swing/latches/reader.py:322` `count_session_recorded_closes`.** Filters `e.data_asof_date = ?` and counts tickers with a usable close, i.e. it counts closes DATED that session by stamp, not PROVEN from it. Already labelled honestly in 21-A ("closes DATED", never "closes FOR"), with the limitation recorded in the docstring. **Unchanged; the label is already correct.**

**Hit 3 — `swing/web/view_models/latches.py:249` `_build_row.price_asof`.** The latch CARD renders the run stamp as the price's as-of date, and `_zone_position` derives IN ZONE / OUT OF ZONE from that price. Mitigated by `price_source="last_close"` and `price_is_stale=True` rendered unconditionally, so it does not claim freshness the way the check did — but it is the same shape one level down. **FOLDED IN by RD, 2026-07-28** — no longer flagged-not-fixed. His ruling: *"One string, same surface, same cycle, and it renders a run-level stamp as a per-row date on the very panel this arc exists to correct — a live instance of gotcha #30 sitting inside the fix for gotcha #30. Paying a second dispatch to leave it there for a week would be indefensible."* It is now a 21-G task with its own discriminating test.

**Hit 4 — `research/harness/aplus_v2_ohlcv_evaluator/context_builder.py:266-290,348` (+ `ohlcv_reader.py`).** The V1<->V2 parity harness reads `er.data_asof_date` per candidate and slices EVERY ticker's OHLCV to `<= data_asof_date` — the COHORT MAX — while V1's own close came from that ticker's OWN last bar. For a ticker that lagged the cohort at V1-eval time, V2 sees a bar V1 never had, and the resulting criterion-level difference is attributed to the evaluator. **A genuine second instance of the structure, in the research measurement chain**, and a third member of the freshness-desync family alongside gotchas #24 (parallel-archive freshness desync) and #26 (archive bar-content temporal mutation). **REPORTED. RD's lane to scope.**

**Hit 5 — `research/harness/backtest_v2_tightness/{run.py:64-79, patterns.py:76-91, walkforward.py:7}`.** The forward walk is anchored on `first_data_asof_date` — "trigger = first session AFTER `first_data_asof_date` where Close > pivot" — again the cohort max rather than the ticker's own last bar, so a lagging ticker's own boundary bar can be included or skipped by one session. Same shape, same lane. **REPORTED.**

**Hit 6 — `research/harness/{r2a_tightness_days_required, r2d_adr_min_pct, v2_orderliness_max_bar_ratio, v2_proximity_max_pct, v2_tightness_range_factor}/cohort_csv.py`.** These use `(ticker, data_asof_date)` as a DEDUPE / IDENTITY key, which is **benign** — a stamp is a perfectly good grouping key. Listed because their emitted cohorts feed walk-forward code that inherits hit 5's anchoring. **REPORTED as inherited, not as an independent defect.**

**Hit 7 — `swing/data/repos/pattern_detection_events.py:119,150`.** The forward-observation gate `d.data_asof_date < observation_date` ("STRICT on the data") uses the CLOCK-derived pipeline stamp as the detection's data cutoff.

**READ AND CORRECTED BY RD 2026-07-29 — full trace at [`docs/rd-d27-provenance-trace.md`](rd-d27-provenance-trace.md) (`ff405567`, corrected `1e285b6a`). The mechanism originally stated here was BACKWARDS, and the "no instance was sought" caveat no longer applies — one was sought, and measured.**

- **A lagging archive makes the gate STRICTER, not weaker.** Stamp `D`, true cutoff `D-3`: the gate admits `obs > D`, which is strictly after `D-3`. No look-ahead is reachable on that path. The real cost is **under-observation** — the forward walk starts late and skips sessions for that detection. Direction safe; **magnitude unmeasured**, and not cheaply measurable (it needs historical archive state that mutates — gotcha #26).
- **The only look-ahead direction is a TWO-CLOCK-READ RACE.** The stamp is `last_completed_session(run_now)` read at **lease acquisition** (`runner.py:609-610`, copied to detections via `lease_data_asof`, `runner.py:1111`), while both bar cutoffs are read at **fetch** time. A run that **straddles a session close** therefore stamps a detection OLDER than the data it saw, and the gate admits an observation on a bar the detector already consumed — genuine look-ahead into the temporal log, which feeds the shadow engine, which feeds T4.
- **Measured: 0 of 140 completed runs, and it is a PROOF rather than a sample.** `last_completed_session` is monotone non-decreasing in time, so equal values at a run's start and finish mean the value was constant throughout and no fetch inside that run could have read a different session. The persisted stamp also equals `last_completed_session(started_ts)` in 140/140, and 3650 detections carry their run's stamp with 0 mismatches.

**Verdict: LATENT, with a characterised trigger and ZERO instances — the temporal log (58,098 forward observations) is not contaminated on this axis.** Forward exposure is small but not zero: the longest run on record is **73.2 minutes** (median 2.33) against a boundary that occurs once per trading day. Cheapest structural fix, if ever wanted: stamp the detection from the same resolved session the bar-cutoff used, rather than from the lease row. **RD's lane; not urgent at 0/140; NOT a 21-G ask.**

## 5. Explicitly NOT hits (checked and cleared)

- `swing/web/price_cache.py:246-260 `_last_close`` — reads `candidates.close` ordered by `e.run_ts` and returns the bare float. It attaches NO date, so it makes no provenance claim. (An UNDATED price is a different and weaker concern.)
- `swing/patterns/foundation.py:767` — joins on `er.action_session_date` (forward-looking, not an aggregate over bars) purely to pick the latest candidate row at-or-before an as-of. No per-row value is dated by it.
- `swing/journal/analyze.py:139` — selects `er.action_session_date` and `c.close` together into `RecommendationContext(eval_run_action_session_date=..., close_at_eval=...)`. The field names do not claim the session dates the close, and the ordering key is `run_ts`. **Adjacent shape, no false claim.** Noted so a future reader does not add one.
- `swing/web/routes/trades.py:809` — sector/industry + `action_session_date`; no price.
- `swing/monitoring/research_health.py:1777`, `swing/web/chart_scope.py:256`, `swing/web/view_models/dashboard.py:201`, `swing/web/view_models/watchlist.py:382,395` — select run IDs only.
- `pipeline_runs.data_asof_date` used AS a run-level fact (lease, briefing header, CLI echo `swing/cli.py:477`) — a run-level stamp used for a run-level purpose is exactly what it is for.

## 6. The answer to RD's question

**It is not one bug, and it is not established to be a class of bugs.**

It is **two** bugs (hit 1 and — on RD's 2026-07-28 ruling — hit 3, both fixed in 21-G), one already-labelled limitation (hit 2), and **three related research-side instances of the same STRUCTURE (hits 4, 5, 7), with UNMEASURED consequences**, which RD owns before the August monthly read. "Related instances of one structure" is what the reading supports; a broader defect family is not claimed, because measuring these three would require running the chains they sit in (Codex R8 MINOR). The structure is demonstrably repeated — a run/batch stamp copied onto per-row records and later read as those rows' own date — which is more than one bug and less than a proven class. Deciding whether hits 4/5/7 are defects requires measuring their effect on results RD owns, which is a scoping question rather than an engineering one.

The write-side observation that makes them one family: **`evaluation_runs.data_asof_date` is an aggregate, and every table that copies it onto a per-ticker row inherits the gap.** Closing it at the source — per-ticker close provenance at write time — is the real fix for the whole family, and is out of 21-G's scope by hard stop (it is a schema / measurement-chain arc of its own, routed to CHARC + RD).
