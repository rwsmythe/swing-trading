# T4 read #3 — the CONFIRMED-NEGATIVE verdict is WITHDRAWN as unsupported

**Author:** RD. **Date:** 2026-08-01 (the August monthly read, watch-standard §1 binding cadence).
**Cited artifact:** `shadow-expectancy-20260801T034118Z`, copied to `artifacts/` per watch-standard **v2.1** (cite = commit).
**Supersedes the verdict of:** [`2026-07-03-broad-watch-baseline-t4-decision-read.md`](../2026-07-03-broad-watch-baseline-t4-decision-read.md) §4 and §8.

> **VERDICT: T4 IS UNDETERMINED.** The prior verdict is **WITHDRAWN, not flipped.** The −0.648 / −0.637 "CONFIRMED-NEGATIVE, FINAL" reads were **not measurements of expectancy** — they were measurements of *how fast losers resolve*. The replacement estimate is positive but far too weak to bank in either direction.

---

## 1. The finding, in one table

The **June detections are a FIXED SET**. Nothing about them changed after 2026-06-30. Measured against successive nightly artifacts, that same fixed cohort reports:

| artifact | % of June cohort closed | June closed-only mean R | `ma_close_below` exits | `breakeven_stop` exits |
|---|---|---|---|---|
| 2026-06-13 | 30.0% | **−1.0000** | 0 | 0 |
| 2026-06-24 | 60.7% | −0.9395 | 0 | 5 |
| 2026-06-30 | 53.3% | −0.9683 | 0 | 6 |
| **2026-07-03** | **58.8%** | **−0.6370** ← *read #1's number* | 2 | 16 |
| 2026-07-08 | 70.2% | −0.3674 | 2 | 40 |
| 2026-07-16 | 91.7% | −0.0883 | 7 | 64 |
| 2026-07-23 | 93.6% | +0.0902 | 10 | 66 |
| **2026-08-01** | **95.3%** | **+0.2129** | 15 | 68 |

**A fixed cohort moved −1.00 → +0.21 purely by aging.** Read #1's −0.6370 sits on that curve at 58.8% closure. Read #2 (07-05) sits beside it.

**The mechanism is visible in the last two columns.** A loser resolves in days at `initial_stop`. A winner takes *weeks* to trail out via `ma_close_below` — that column is **0 until July** and reaches 15 only by August. So a young cohort's closed set is nearly pure stop-outs, and its mean is a measurement of resolution speed rather than of edge.

## 2. Why the prior verdict must be withdrawn rather than restated

The frozen 0026 criterion gates on **N ≥ 30 priced shadow signals**. It says nothing about **maturity** — and maturity dominates the estimate by roughly **1.2R**. Applying the criterion to an immature cohort produces a number with no expectancy content.

Read #1 was executed correctly against the criterion as written. **The criterion was underspecified, and neither read could have known it without this longitudinal series**, which did not exist until enough artifacts accumulated to plot it.

The "FINAL" label attached on 07-05 meant *survived the engine fix*. It was already flagged (2026-07-29) as overselling stability. This read establishes that the underlying number was not a stable quantity at all.

## 3. The replacement estimate — positive, and NOT bankable

Maturity-filtered, closed-only, realistic arm, age in NYSE sessions since detection:

| gate | n | names | mean R | win rate | Wilson LB |
|---|---|---|---|---|---|
| ≥ 0 (the pooled headline) | 347 | 84 | −0.2120 | 24.5% | 20.3% |
| ≥ 10 | 308 | 78 | −0.1193 | 26.6% | 22.0% |
| ≥ 20 | 212 | 64 | **+0.1064** | 27.8% | 22.2% |
| ≥ 25 | 144 | 49 | **+0.2544** | 34.7% | 27.4% |
| **≥ 30** | **76** | **32** | **+0.2020** | 39.5% | 29.2% |
| ≥ 35 | 25 | 12 | −0.4178 | 28.0% | 14.3% |

**Mature (≥30) non-ETF: n=68, 30 names, mean +0.3434, win 44.1%, Wilson LB 32.9%.**

**Why this is NOT banked, and the skepticism is deliberate** — this result runs in the *flattering* direction, so it gets the same treatment read #1 applied to the mtm number that ran the other way:

- **ONE market window.** The mature cohort's detections span **2026-06-05 → 2026-06-17** — thirteen calendar days. A single favorable regime reproduces this result entirely.
- **Correlated samples.** 76 rows over 32 names = 2.4 detections per name, walking overlapping bars.
- **Unstable at the tail.** The ≥35 band inverts to −0.4178. Small-n, but it is exactly the instability that forbids treating +0.20 as converged.
- **Not independent of read #1.** This is largely the *same cohort* re-measured, not a fresh sample.

The one direction that is *not* a concern: 5 mature rows are still open and are **excluded** from the mean, so if winners linger the +0.20 is conservative.

## 4. What IS strong — the leveraged-ETF slice

| | n | names | mean R | wins | exit mix |
|---|---|---|---|---|---|
| leveraged ETFs | **38** | 6 | **−0.9746** | **0 / 38** | **`initial_stop` × 38** |

`AMDL, SVIX, TNA, TSMX, UDOW, URTY` — identified from `candidates.industry = 'Exchange Traded Fund'`, not by ticker guessing. **Every one of the 38 detections exited at the initial stop. Not one reached breakeven.**

**Note this corrects the banked ETF cut**, which used only `TNA/URTY/UDOW` (3 names). The real leveraged slice is **6 names / 38 rows / 11.0%** of the closed cohort.

This is a **universe-composition** question, not a strategy-edge claim: leveraged index and single-stock ETFs are structurally unsuited to a swing-breakout screen (daily-reset decay, no base structure, no earnings/fundamental driver). It does **not** meet the V2.1 promotion gate (≥30 signals **and** ≥6 months — we have the signals, not the months), so it is a **candidate**, not a deployment.

## 5. What I am asking for

1. **The T4 verdict is withdrawn.** The registry's frozen criterion stands untouched; what changes is that no verdict is currently supported by it.
2. **The watch standard needs a MATURITY GATE for T4 reads** — a decision read may not be executed on a cohort below a stated closure threshold. On this evidence, ~95% closure (≈30 sessions) is where the June curve flattened. That is a **read-discipline amendment**, not a code change, and it is mine to draft.
3. **Emit `entry_fill` and `pivot` in `results.csv`** — already asked for separately; it also makes the uncapped-fill divergence measurable.
4. **No posture change.** Stop-engineering plus market time still holds: nothing here is an engineering demand, and the correct response to "the cohort is immature" is to let it mature.

## 6. Honest statement of what this does and does not establish

It does **not** establish that the watch pool is profitable. It establishes that **the number we banked as evidence it was unprofitable was measuring something else**, and that the honest current answer is *we do not yet know*.

The A+-selectivity validation that rested on T4 being negative is **weakened accordingly** — not refuted, but no longer supported by this evidence.
