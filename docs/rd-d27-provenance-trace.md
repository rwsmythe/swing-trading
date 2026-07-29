# RD trace — D27 and survey hits 4 / 5 / 7 (the run-level-stamp shape inside the research measurement chain)

**Author:** RD. **Performed:** 2026-07-28 (local HST; UTC 2026-07-29), read-only against main `feeb0703` and the live DB.
**Provenance note on this trace itself:** part of the code reading was performed with the shell CWD inside the `phase21-g-provenance` worktree. Before publishing, all seven traced files (`orchestration.py`, `runner.py`, `prices.py`, `ohlcv_cache.py`, `pattern_detection_events.py`, `dates.py`, `pipeline/ohlcv.py`) were confirmed **byte-identical** to main by `git hash-object`, and 21-G's diff was confirmed to touch only `swing/latches/*` plus latch templates/VMs. The branch-sensitive commands (§5's chain dates and coupling grep) were re-run from main. Recorded rather than quietly corrected, because a trace that cites the wrong tree is exactly the class of defect this document is about.
**Obligation discharged:** the RD-owned deadline in [`docs/rd-state.md`](rd-state.md) §5 — *read survey hits 4, 5 and 7 BEFORE the August monthly read, because that read consumes the chain they sit in.*
**Source of the hits:** the 21-G `data_asof_date` consumer survey (`docs/data-asof-date-consumer-survey-21g.md` — **currently on the `phase21-g-provenance` branch, not yet on main**; it lands with 21-G).
**Shape under investigation:** cumulative gotcha **#30** — *a run/batch-level stamp is not provenance for a per-row value.*

**Evidence discipline:** every figure below was queried fresh this session. Where I correct the survey, I correct the MECHANISM and keep or sharpen the hazard — per the survey's own instruction that these hits *"may be corrected but may not be softened."*

---

## 1. Headline

**The August read's chain is CLEAN on this axis, and that is now a measurement rather than an assumption.**

- **D27 (the naming collision) is REAL as a readability defect and is NOT producing divergence.** The two columns agreed in **113 of 113** paired runs across the entire history — not the 25 previously sampled — and the agreement is **structural, not luck** (§3).
- **Hit 7 (the forward-observation gate) has ONE genuine look-ahead path, and the survey named the wrong mechanism for it.** The real path is a two-clock-read race, not a lagging archive. Measured across all 140 completed runs: **zero occurrences, provably** (§4).
- **Hits 4 and 5 are NOT deadline-bound by the August read.** They sit in dormant harnesses the read does not run (§5). The deadline rationale was true of hit 7 only.

---

## 2. The two write paths — confirmed on disk

| column | derivation | when |
|---|---|---|
| `evaluation_runs.data_asof_date` | `max(max_dates).date()` over per-ticker OHLCV last-bar dates — **BAR-derived, cohort max** | AFTER the fetch (`swing/evaluation/orchestration.py:229-231`) |
| `pipeline_runs.data_asof_date` | `last_completed_session(run_now)` — **CLOCK-derived** | BEFORE any bar is fetched, at lease acquisition (`swing/pipeline/runner.py:609-610`) |

`pattern_detection_events.data_asof_date` is a **copy of the CLOCK-derived pipeline stamp**, read back from the `pipeline_runs` row by `lease_data_asof` (`runner.py:1111-1121`) and stamped onto every per-ticker detection (`runner.py:2602`, `:2833`). Verified empirically as well as structurally: **3650 detections joined to their run, 0 stamp mismatches.**

## 3. Why the two columns have never diverged — the mechanism, which is not the one I expected

Both consumers of bar data are **capped at the clock session at fetch time**:

- **Evaluation path** — `PriceFetcher.get` (`swing/prices.py:56-68`) resolves `effective = _resolve_asof(None) = last_completed_session(datetime.now())` and slices `df.index.date <= effective`. So `max(max_dates)` **cannot exceed** the clock session. (Note: the evaluation does *not* go through `swing/pipeline/ohlcv.py`'s `iloc[:-1]` strip — that helper is a different path. Checking this mattered: my first hypothesis named the wrong file.)
- **Detector path** — the detector uses a **different** bars source, `OhlcvCache.get_or_fetch` (`swing/web/ohlcv_cache.py:293-310`), which strips any bar `> end` and slices `<= end`, where `end` is likewise `last_completed_session(now())`.

So the bar-derived value is **clock-capped on both paths**, and the cohort max over hundreds of tickers keeps it from falling short. That is why the columns agree, and it is a property of the code rather than of healthy nightlies.

**Measured:** 113 paired `pipeline_runs`↔`evaluation_runs` rows, **113 agree, 0 diverge in either direction** — including **17 runs started during US market hours** (03:00–09:59 HST), which is where the partial-bar hazard would have shown up.

**D27 therefore stands as a NAMING defect, not a value defect.** Two quantities share one column name; a reader cannot tell which they hold; nothing enforces the agreement. The reason to fix it is that the schema misleads, which is true regardless of whether the values have diverged yet.

## 4. Hit 7 — the mechanism corrected, the hazard sharpened, the incidence measured

The gate (`swing/data/repos/pattern_detection_events.py:113-156`) admits an observation when `d.data_asof_date < observation_date`, documented as *"STRICT on the data cutoff; the forward-walk starts the first COMPLETED session AFTER the detector's DATA CUTOFF."*

**The survey's stated mechanism is backwards.** It reads: *"If a ticker's actual last bar were older than that clock session, the gate is weaker than its own comment claims."* Trace the direction:

- **Stamp NEWER than the ticker's true cutoff** (the lagging-archive case the survey names): stamp `D`, true cutoff `D-3`; the gate admits `obs > D`, which is strictly after `D-3`. The gate is **STRICTER than necessary, not weaker.** No look-ahead. The real cost is **under-observation** — the forward walk starts late and skips sessions `D-2 … D` for that detection. Direction is safe; **magnitude unmeasured**, and not cheaply measurable because it needs historical archive state that mutates (gotcha #26).
- **Stamp OLDER than the true cutoff** — this is the only look-ahead direction, and it is where the actual hazard lives.

**The real look-ahead path is a two-clock-read race.** The stamp is `last_completed_session(run_now)` where `run_now` is read at **lease acquisition**; both bar-cutoffs are `last_completed_session(datetime.now())` read at **fetch time**. Same quantity, two reads, separated by the run's own duration. If a run **straddles a session close** (16:00 ET), the fetch-time read is one session newer than the lease-time read → the detector sees bar `D` while the row is stamped `D-1` → the gate admits an observation on a bar the detector already consumed. That is genuine look-ahead contamination of the temporal log, which feeds the shadow engine, which feeds T4.

**Measured — and it is a proof, not a sample.** `last_completed_session(t)` is monotone non-decreasing in `t`, so if the value is equal at a run's start and finish it is constant throughout, and no fetch inside that run could have read a different session. Across **all 140 completed runs**: **0 straddles**, and the persisted stamp equals `last_completed_session(started_ts)` in **140/140**.

**Verdict: a latent hazard with a now-characterised trigger and ZERO observed instances. The temporal log (58,098 forward observations) is not contaminated on this axis.** The exposure is not zero going forward — the longest run on record is **73.2 minutes** (median 2.33), so a slow run started shortly before the close boundary could hit it.

## 5. Hits 4 and 5 — real instances, but NOT in the August read's path

| | chain | last touched | consumed by the monthly read? |
|---|---|---|---|
| Hit 4 | `research/harness/aplus_v2_ohlcv_evaluator/` (V1↔V2 parity) | 2026-05-25 | **No** |
| Hit 5 | `research/harness/backtest_v2_tightness/` (forward walk on `first_data_asof_date`) | 2026-05-24 | **No** |
| — | `research/harness/shadow_expectancy/` (what the read DOES consume) | 2026-07-04 | yes |

There is **no coupling** — the shadow-expectancy engine imports neither harness; the only reference to hit 4's package anywhere in `swing/` is an operator-invoked CLI entry point (`swing/cli.py:5652`). Both chains predate the 2026-05-27 applied-research arc closure (which produced zero deployable yield) and are dormant.

**Consequence for the deadline:** the rationale *"that read consumes that chain"* was true of hit 7 and **not** of hits 4 and 5. They are not dismissed — they remain real instances of the #30 structure, and each would bias a V1↔V2 criterion-level comparison by attributing a boundary-bar difference to the evaluator. But they are a **precondition on any future USE of those harnesses**, not a blocker on the August read. Anyone re-running either harness, or citing a parity claim from it, must price hits 4/5 first.

## 6. What I am NOT claiming

- Not that D27 is harmless — it is a live readability defect in a schema two of my monitors read (CALIBRATION C's whole-session-miss clause keys the clock-derived value; the detection/observation surfaces carry the bar-derived one).
- Not that hit 7 is closed — it is *uninstantiated*, which is a different and weaker statement. The clock-cap makes the common case safe; the straddle race remains open.
- Not that the under-observation direction is negligible — its direction is safe and its magnitude is **unmeasured**.
- Not that hits 4/5 are benign — only that they are not on the August read's critical path.

## 7. Carried forward

1. **August monthly read #2** may proceed on this axis without qualification: the consumed chain is measured clean.
2. **The straddle race** is the only live look-ahead path. Cheapest structural fix is to stop taking two clock reads — stamp the detection from the same resolved session the bar-cutoff used, rather than from the lease row. Scoping is CHARC's; it is not urgent at 0/140.
3. **D27's naming fix** (two quantities, one column name) stays scoped to the Phase-21 close or Phase 22.
4. **Hits 4/5** re-scope from *deadline-bound* to *precondition on re-use of those harnesses*.
