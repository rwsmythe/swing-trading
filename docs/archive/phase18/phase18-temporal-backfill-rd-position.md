# RD independent position — the temporal-log backfill track (103 NaN rows)

**Author:** Research Director (RD). **For:** CHARC's reconciliation (RD read + Codex read + CHARC read → operator synthesis).
**Date:** 2026-06-13. **Thread:** phase18-temporal-backfill. **Status:** genuine independent position, written without seeing CHARC's or Codex's analysis (anti-anchoring, as requested).

**Bottom line:** Ship the writer fix (unambiguous). **Do NOT backfill the 103 rows.** The recoverable evidence is ~1 genuinely-unique priced name against the cost of puncturing the immutability guarantee; the math does not justify it. Default-to-no holds even before weighting the precedent risk.

---

## The decisive evidence (read-only, live DB, 2026-06-13)

I verified the backfill's actual payoff rather than assuming it.

1. **18 of 19 NaN-tickers do NOT re-detect cleanly.** They were detected in the 06-05/06-08 window, fell off the screen, and have zero post-06-10 detections. Only **UCTT** re-detects cleanly (5 clean post-06-10 detections). So for 18 names the 06-10-spanning detection is the only record — *not* a correlated duplicate. (This corrected my initial assumption that the loss was redundant copies.)
2. **But only 2 of 19 would ever TRIGGER (price).** The entry rule keys on `high` (present, not NaN), so I computed it exactly: only **COHU** (maxHigh 61.80 ≥ pivot 58.47) and **UCTT** (110.25 ≥ 94.95) reach their pivot. The other **17 never trigger** — they are 0R `never_triggered`, which contribute nothing to the priced-signal gate.
3. **The gate counts TRIGGERED signals.** Migration 0026 freezes "mean R … on closed_only and mtm_at_horizon at **N≥30 priced shadow signals**"; the scorecard defines priced = `triggered and realized_r is not None`. So `never_triggered` do not count toward N≥30.
4. **Net recoverable toward the gate: ≈1 genuinely-unique priced name (COHU).** UCTT is already captured by its clean post-06-10 detections (redundant). We are at 10 priced signals / 4 names; backfill takes us to ~12 / ~5. **Immaterial.**

---

## CHARC's four questions

### 1. Full reasoning — FOR and AGAINST

**FOR backfill:** 18 of 19 names don't re-detect, so without backfill they are permanently lost; COHU is a genuine priced name that triggered and will never self-heal (validate_bars rejects the whole chain for one interior NaN, forever); the writer fix does nothing for the existing 103; in a sample-starved program every priced signal has scarcity value.

**AGAINST backfill:** the FOR case collapses on the numbers — 17 of 19 are 0R non-triggers, so the real recovery is ~1 unique priced name (COHU); UCTT is redundant; mutating an object whose entire design purpose is immutability sets a precedent that erodes the anti-drift reproducibility guarantee; a backfilled close sourced from a *current* fetch reintroduces exactly the historical-bar drift (gotcha #26, 0.5–3%) the immutable log exists to prevent; it costs a migration + a governed mutation path + an operator gate; and the recovered cohort is a biased subsample (older fizzles), so it's not even "free clean data."

The asymmetry decides it: not-backfilling costs ~1 name and is **recoverable by time** (the gate is market-time-gated); backfilling-wrong costs the immutability guarantee and is **not easily recoverable**. Favor the reversible path.

### 2. Concerns about mutating the immutable log — what's at stake, and weight

The temporal log's purpose is **anti-drift reproducibility**: it freezes the bars as-of detection so the shadow measurement is deterministic and immune to yfinance re-fetch drift (it is the project's answer to gotcha #26). What's at stake:
- **Reproducibility:** post-backfill runs no longer reproduce pre-backfill artifacts. Manageable if dated/audited, but a real break.
- **Precedent (the part I weight HIGH):** "we mutate the substrate when we judge the data wrong" is a slippery slope. Applied once narrowly it's defensible; established as a pattern it reintroduces the drift immutability was built to exclude. The guarantee is binary — it's either immutable or it's "immutable except when we decide otherwise," and the second is worth much less.
- **Narrow defensibility:** a NaN→real-close fill is the *least* objectionable possible mutation (no good as-of value is being overwritten — there was never a finite 06-10 close stored). So *if* it were ever done, the bar must be: NaN-only (never overwrite a finite value), dated, audited, provenance-stamped, and sourced from the as-of archive if it captured 06-10 — not a fresh re-fetch.

I weight the precedent risk **heavily** relative to a ~1-name payoff. The guarantee is a strategic asset of the measurement program; spending it for one correlated-ish sample is a bad trade.

### 3. Decision criterion + default

**Criterion:** backfill is worth it ONLY IF (a) the recoverable *independent priced* evidence is material to the N≥30 gate, AND (b) the repair is NaN-only / audited / sourced from the as-of archive (minimal drift). Condition (a) fails on the data (~1 unique priced name). So: **don't backfill.**

**Default if ambiguous: DON'T.** The immutability guarantee outweighs a handful of samples; the cost of waiting is recoverable, the cost of eroding the guarantee is not. A research-director should err toward preserving the integrity of the measurement substrate over squeezing marginal N.

### 4. Is the attrition BLOCKING N≥30, or merely delaying?

**Delaying, marginally — not blocking.** Recoverable toward the gate is ~2 triggered signals (10→~12 of 30). The path to 30 is dominated by **future breakouts**, not by recovering 19 historical mostly-fizzles. The attrition does not gate the decision; market time does.

One caveat that stands **regardless of the backfill decision** and belongs in the eventual T4 read: the excluded cohort triggers at ~2/19 (11%) vs the included 10/33 (30%), because it's older names that fizzled. So the invalid_ohlc exclusion mildly **inflates the observed trigger rate**. Meaningless at N=10, and a small fraction by N≥30 — but note it when T4 fires.

---

## Recommendation to CHARC

1. **Ship the writer fix.** Stops the bleeding; unambiguous; preserves immutability going forward.
2. **Do not backfill.** Let the 103 age out — they're honestly excluded, the recovery is ~1 unique priced name, and the precedent cost is real.
3. **If the operator still wants COHU-class recovery,** the correct lever is NOT mutating the substrate — it's an *analysis-layer* option (teach the engine to price a chain with a single interior NaN bar by using the valid high/low and skipping the NaN close for MTM/MA). That preserves immutability. But I do not recommend even this for ~1 name — it adds the NaN-propagation complexity I flagged (MA-trail suppression / partial-skip) for negligible gain. **Simplest correct answer: accept the loss.**
4. **Surface the excluded-reason breakdown** (the observability half of brief 1 / the health monitor) regardless — so the next such event is visible same-day.
