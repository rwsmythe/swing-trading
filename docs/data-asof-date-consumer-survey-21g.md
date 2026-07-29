# The `data_asof_date` consumer survey (Arc 21-G)

**Commissioned by:** the 21-G brief §2.4 (`docs/provenance-asymmetry-21g-commissioning-brief.md`). **Performed:** 2026-07-28, at writing-plans, against main `1955aa59` (schema v32) and the live DB + prices cache, read-only. **Duplicated verbatim as §S of** [`docs/superpowers/plans/2026-07-28-phase21-arc-g-provenance-asymmetry.md`](superpowers/plans/2026-07-28-phase21-arc-g-provenance-asymmetry.md) so the plan is self-contained; this file exists because a plan is archived after execution and a director needs a stable thing to cite.

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

They agreed in **25 of the last 25 paired runs**. That is a property of healthy nightlies, not an invariant — nothing enforces it, and the two are computed from different inputs at different times. RD's framing, preserved verbatim:

> *"worse than a latent hazard — a hazard that LOOKS CORRECT. A reader who conflates them is not being careless; the schema is telling them the two are the same thing. And they diverge precisely when the archive lags, which is the Route B condition, so the collision and the hazard fire together."*

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

**Two different quantities share one name.** Empirically they have never diverged: across the last 25 paired runs, `pipeline_runs.data_asof_date == evaluation_runs.data_asof_date` in **25/25**. That is a coincidence of a healthy nightly, not an invariant — nothing enforces it, and the two are computed from different inputs at different times.

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

**Hit 7 — `swing/data/repos/pattern_detection_events.py:119,150`.** The forward-observation gate `d.data_asof_date < observation_date` ("STRICT on the data") uses the CLOCK-derived pipeline stamp as the detection's data cutoff. If a ticker's actual last bar were older than that clock session, the gate is weaker than its own comment claims. **REPORTED. RD's lane (the temporal log is his measurement chain).** No instance was sought or found; the point is that the guarantee is asserted, not enforced.

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
