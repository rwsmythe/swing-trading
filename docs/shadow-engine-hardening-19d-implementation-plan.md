# Shadow-Engine Hardening (19-D) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the shadow-expectancy engine's zero-floor risk-unit guard with a meaningful, live-calibrated risk floor, and add a reader-side epsilon-tolerant OHLC clamp that recovers signals lost to sub-cent shape violations — both purely inside `research/harness/shadow_expectancy/`, reader-side only, retroactive by pure re-run.

**Architecture:** Two independent measurement-policy changes plus one analysis task. (a) A **risk-unit floor** in `simulator.simulate`: a mechanical risk-per-share below a fraction of the candidate's screening ADR is treated as `degenerate_risk` (the same existing exclusion terminal), because a near-zero denominator inflates R without bound. (b) An **epsilon-tolerant reader clamp** applied at the bar-read boundary (after collapse, before `validate_bars`): a shape violation (`low > min(o,c)` or `high < max(o,c)`) whose magnitude is `<=` a small % of price is clamped by *widening* the bar (`high = max(h,o,c)`, `low = min(l,o,c)`); above threshold it stays `invalid_ohlc` exactly as today. The immutable temporal log and the OHLCV archive are untouched — the clamp is engine-internal, reader-side, per-run. (c) A **capture-timing trace** (analysis only, no production code) correlating the ragged-bar dates against capture/write timing and the cross-vendor Schwab-side rejections.

**Tech Stack:** Python 3.14, stdlib `sqlite3` (read-only `mode=ro` URI), pytest. No new dependency. No schema change (v31 frozen). No `swing/` edit.

---

## Global Constraints

Copied verbatim from the commissioning brief ([`docs/shadow-engine-hardening-19d-commissioning-brief.md`](shadow-engine-hardening-19d-commissioning-brief.md)) §3 Locks and §2 Requirements. **Every task's requirements implicitly include this section.**

- **Pure recompute preserved EXACTLY.** Read-only connection (`io.open_ro`, `mode=ro`). ZERO INSERT/UPDATE. A fresh timestamped `exports/research/shadow-expectancy-<ts>/` artifact per run. No write-side or archive mutation anywhere.
- **NO `swing/` edit.** Every file touched is under `research/harness/shadow_expectancy/` or `tests/research/shadow_expectancy/`. The 18-A / 18-B archive-boundary finiteness semantics are OUT of scope — the clamp is engine-internal.
- **NO schema change.** Schema stays v31; `tests/research/shadow_expectancy/testkit.py:make_db` continues to build to `target_version=27` (the tables the harness reads existed by then; `candidates.adr_pct` exists from migration 0001).
- **The immutable log + OHLCV archive stay VERBATIM.** The clamp is READER-SIDE only — it mutates the in-memory `Bar` list the engine walks, never the persisted `pattern_forward_observations.ohlc_today_json` nor any parquet.
- **The 0026 frozen T4 criteria are untouched.** No change to `hypothesis_registry`, attribution, funnel taxonomy, censoring scenarios, or `PARTIAL_SESSION_N=3`.
- **L2 lock preserved.** No new Schwab REST endpoint; `manifest.json` keeps `l2_lock_preserved: true`; `tests/research/shadow_expectancy/test_l2_lock.py` stays green.
- **R values CHANGE by design** — that is the point. Comparability is re-established by the full-corpus re-run + RD's confirmatory re-read, never by patching history.
- **RD RULES the semantics.** The four measurement-policy parameters below (floor form/value, epsilon threshold, exclude-vs-winsorize, CALY-class posture) are PROPOSED here with live-distribution evidence for RD to rule at plan-stage review. The constants land with the recommended defaults; **the executing implementer plugs in RD's ruled value before the final commit.** The T1/T2 discriminating tests read the *shipped* constant, so any value inside the live-derived safe gap passes; a calibration-guard test pins the gap.
- **Conventional commits, ZERO `Co-Authored-By`, no `--no-verify`, no amend.** Test-file lint out of scope; match existing test style (<=100-char lines, local imports).

---

## Measurement-Policy Proposal (RD RULES at plan review)

All evidence below was read from the live DB (`~/swing-data/swing.db`, `mode=ro`) on 2026-07-04, reconstructing the harness pipeline (source=`pipeline`), and from the artifacts under `exports/research/shadow-expectancy-20260630T010654Z`. Every proposed threshold is derived from this distribution, not intuition.

### (a) Risk-unit floor — FORM

**The binding distinction (brief §2/§4), reconstructed from the live DB:**

| signal | pivot | entry bar O/H/L/C | rps = entry_fill - low | rps % of entry | rps / ATR(chain) | **rps / ADR** (`adr_pct`) | verdict |
|---|---|---|---|---|---|---|---|
| **VSTS** 06-25 A+ | 13.560 | 13.600 / 14.020 / 13.555 / 13.740 | **0.045** | 0.331% | 0.0689 | **0.0794** (adr 4.168%) | **must be CAUGHT** |
| **TVTX** 06-12 watch | 49.680 | 49.100 / 52.720 / 48.980 / 52.040 | **0.700** | 1.409% | 0.3525 | **0.2970** (adr 4.744%) | **must SURVIVE, R unchanged** |

**Why rps-%-of-price ALONE is REJECTED (load-bearing — this is the trap):** the live distribution's smallest-rps%-of-price signals include *healthy low-priced names*, not artifacts:

| signal | rps % of entry | rps / ATR | rps / ADR | note |
|---|---|---|---|---|
| CPRX 06-26 | 0.095% | **0.75** | ~0.7 | tiny %, but a healthy stop in volatility terms — NOT collapsed |
| CNTA 06-05/08/09 | 0.500% | **1.28–1.35** | ~1.3 | low-priced, very healthy stop — NOT collapsed |
| OGN 06-26/29 | 0.22–0.30% | 0.45–0.62 | ~0.5 | healthy — NOT collapsed |

A pure %-of-price floor set to catch VSTS (0.33%) would falsely exclude CPRX/OGN/CNTA (real, tradeable stops on cheap stocks). **A volatility-normalised discriminator is required.**

**PROPOSED FORM (RD rules): rps as a fraction of the candidate's screening ADR** — `rps / (adr_pct/100 * entry_fill) < RISK_FLOOR_ADR_RATIO` → `degenerate_risk`.

Rationale for ADR over a recomputed ATR:
- `candidate.adr_pct` is **already stored** on the candidate row (migration 0001) and flows through `io.resolve_candidate` — no new bar math, no ATR-window ambiguity (chains are often only 6 bars, e.g. VSTS).
- It is a **pre-committed, screening-time** volatility measure, uncontaminated by post-entry action.
- **100% populated** on the live corpus (0 null / 0 `<=0` across all 1775 shadow-relevant candidate rows; min 0.136%, median 4.61%). **Null/`<=0` adr → the floor is DISABLED (graceful degrade to the old zero-floor), NOT a %-of-price fallback.** Rationale: (1) a %-of-price floor is the misclassifying form this section explicitly rejects (it would catch healthy low-priced names) — using it as a fallback would reintroduce that exact defect; (2) adr is 100%-populated in production, so a fallback would NEVER fire there and exists only to perturb null-adr TEST fixtures — disabling the floor on null-adr makes every legacy fixture behave EXACTLY as pre-19-D (structurally zero blast radius); (3) a signal you cannot volatility-normalize is left unfloored and, if it were ever a real collapsed-risk artifact, its extreme R would still surface exactly as today (the honest degrade per the schema-boundary-defensive-scope discipline — degrade gracefully, do not invent a mismatched guard).

`rps/ATR` (ATR recomputed from the forward bars) is a documented **alternative** RD may prefer — it matches the "~0.07x ATR" framing literally but carries the short-chain window fragility. If RD picks it, the executing implementer swaps `_min_risk_per_share`'s ADR term for an `atr_from_forward_bars(...)` term; the tests are unchanged in structure (VSTS still catches at 0.069, TVTX still survives at 0.353).

### (a) Risk-unit floor — VALUE

The binding gap on the proposed `rps/ADR` discriminator is **(0.079, 0.256)** — anything strictly above VSTS (0.0794) and strictly below TVTX (0.2970, or its tighter re-detection 0.2564 at run 101) catches VSTS and spares TVTX. Sensitivity across the live corpus (which signals get excluded at each candidate ratio):

| `RISK_FLOOR_ADR_RATIO` | additionally excluded (beyond the pre-existing zero-floor) | notes |
|---|---|---|
| 0.10 (conservative) | VSTS only | catches only the clearest collapse |
| **0.15 (RECOMMENDED default)** | VSTS, ARMK-tight (runs 109-113, 0.145-0.148), PGNY-tight (run 113, 0.164) | the genuinely-collapsed cluster; well clear of TVTX 0.256 |
| 0.20 (moderate-aggressive) | + ULCC (0.172), BBGI (0.176) | **false-positive risk**: BBGI rps%=2.16% is a genuinely WIDE stop on a very-volatile name (adr 12.28%) |
| 0.25 (aggressive) | + CVS (0.20-0.21), M (0.231) | encroaches on TVTX's neighborhood; not recommended |

**Recommended default: `RISK_FLOOR_ADR_RATIO = 0.15`** — it catches the genuinely-collapsed subclass (VSTS + the tight ARMK/PGNY re-detections) and sits cleanly below TVTX. **RD rules the final value.**

**Decision-relevant nuance for RD:** the T4-study "artifact class" (VSTS/PGNY/DFTX/LTH/ARMK) is NOT monolithic on the denominator. Only a *subset* has collapsed risk units. **DFTX +14.29R** has rps=1.43 (**5.67% of price**, rps/ADR=0.95) — a *wide* stop; its large R is a genuine large move, not a collapsed denominator. **LTH** (rps/ADR 0.41-0.78) and the non-tight ARMK re-detections (rps/ADR 0.68-1.24) are likewise NOT denominator-collapsed. The floor's job is the collapsed subclass (VSTS, ARMK-tight, PGNY-tight); it should NOT and does not catch DFTX/LTH at any value inside the safe gap. RD should calibrate to the collapse, not to "every large-R mark."

### (c-of-§2) Exclusion vs winsorize — SEMANTICS

**PROPOSED (RD rules): EXCLUDE as `degenerate_risk`** (the existing taxonomy reason — no new string, matches the brief's "prefer the EXISTING taxonomy").

Evidence that winsorizing at the discriminator threshold does NOT tame the artifact: winsorizing VSTS's rps up to the floor (`min_rps = 0.15 * 0.1668... ADR-price ≈ 0.085`) still prices the +27.3R mark (price 14.83) at `(14.83 - 13.60) / 0.085 = 14.5R` — only *halved*, still wildly inflated. To winsorize VSTS to a "sane" single-digit R you would need a floor so high it would also catch TVTX. **A degenerate denominator makes R unmeasurable; the honest posture is to drop the signal, not invent a denominator.** If RD instead rules WINSORIZE (to retain the signal in trigger-rate / denominators), the code variant is given in Task 2 (replace the degenerate return with `rps = max(rps, min_rps)` and continue).

### (b) Epsilon-tolerant reader — THRESHOLD + (d) CALY-class posture

Every OHLC shape violation in the live corpus (source=`pipeline`), by clamp magnitude (`max(low - min(o,c), max(o,c) - high)` as % of close), 16 distinct bars / 13 tickers:

| clamp % | count | tickers (bar date) |
|---|---|---|
| 0.037 – 0.101 | 5 | OGN, M, RSI, VOYA, EVC |
| 0.144 – 0.253 | 4 | VSTS (06-12), MFG, RLJ |
| 0.330 – 0.470 | 5 | NSA (×2), DINO (×3), VIRT |
| 0.531 – 0.771 | 2 | NSA (07-01), TLYS |
| **1.664** | **1** | **CALY (07-01)** — the lone outlier |

The tight cluster spans **0.037% – 0.771%** (15 bars); **CALY sits alone at 1.664%**, separated by a ~0.9-point gap. Non-finite bars (103 in the corpus) and negative bars are a SEPARATE class — they are NOT clampable (you cannot widen a NaN) and stay `invalid_ohlc`.

**PROPOSED (RD rules): `OHLC_CLAMP_MAX_PCT = 1.0`** — sits in the (0.771%, 1.664%) gap, clamps the entire tight cluster (15 bars recovered), and isolates CALY as the sole residual `invalid_ohlc`. Sensitivity:

| `OHLC_CLAMP_MAX_PCT` | clamped (recovered) | left `invalid_ohlc` |
|---|---|---|
| 0.5% | 13 bars | TLYS (0.771), NSA-0701 (0.531), CALY (1.664) |
| **1.0% (RECOMMENDED)** | 15 bars | **CALY (1.664) only** |
| 1.5% | 15 bars | CALY (1.664) only |
| 2.0% | 16 bars | none — CALY clamped too |

**(d) CALY-class posture — RD rules whether CALY stays excluded.** The default (1.0%) leaves CALY excluded (its 1.66% distortion is genuinely large relative to the cluster). If RD wants CALY recovered too, ruling `>= 1.7%` clamps it. The clamped-bar counter in the artifact (Task 6) lets RD watch this inflow every run without re-probing the DB.

### Capture-timing preliminary evidence (informs Task 8, the analysis)

- All 16 ragged bars carry `provider = yfinance`, captured **same-evening HST** by the nightly pipeline (`created_at` ~6h after the session close, e.g. CALY 07-01 captured 07-02T02:00Z = 07-01 16:00 HST).
- They cluster on specific session dates, with a heavy **07-01 burst (7 of 16 bars)** — a single-session multi-ticker event points at a provider-side data-quality episode, not per-ticker noise.
- **Cross-vendor corroboration:** `schwab_api_calls` for run 123 (and run 121) carry 9 Schwab-side `marketdata.pricehistory` "OHLC consistency: OhlcvBar invariant violated" rejections (rejected at the 18-B ladder ingest barrier) — the ragged-bar phenomenon is multi-provider, not a yfinance bug. This supports the reader-clamp locus: the raw log is correctly recording verbatim; the excess is in the read-side all-or-nothing.

---

## File Map

**Modify (all under `research/harness/shadow_expectancy/`):**
- `constants.py` — add `RISK_FLOOR_ADR_RATIO`, `OHLC_CLAMP_MAX_PCT`, `CLAMP_SAMPLE_LIMIT` (measurement-policy constants; RD-ruled values).
- `simulator.py` — `SimParams` gains ONE floor field `risk_floor_adr_ratio` (defaulted 0.0 = disabled); `simulate` gains `adr_pct` kwarg (default `None`); a `_min_risk_per_share` helper; the degenerate guard tightens from zero-floor to the risk floor.
- `validate.py` — add `clamp_ragged_bars(bars, *, max_pct) -> tuple[list[Bar], list[ClampEvent]]` + a `ClampEvent` dataclass + a shared `_shape_violation_pct` helper (co-located with `validate_bars`, reusing `_finite_nonneg`).
- `run.py` — pass `candidate.adr_pct` and the floor constant into `simulate`; set the `SimParams.risk_floor_adr_ratio` field from `RISK_FLOOR_ADR_RATIO`; call `clamp_ragged_bars` on `all_bars` after the `missing_observations` guard and before `validate_signal`; accumulate the distinct-bar dict + the event total; thread a `clamp_summary` into the manifest + summary.
- `output.py` — no change (manifest/summary writers already accept arbitrary dicts / line lists).

**Test (all under `tests/research/shadow_expectancy/`):**
- `test_simulator.py` — T1 (VSTS caught), T2 (TVTX survives), T3 (normal-stop unchanged), plus the `_min_risk_per_share` unit + the fallback path.
- `test_validate.py` — clamp-math unit tests: T4-math (DINO clamped at 1.0%), T5-math (CALY not clamped at 1.0%, clamped at 2.0%), non-finite passthrough, above-threshold passthrough, idempotence, no-new-`high<low`.
- `test_real_shapes.py` — T4 (DINO recovered end-to-end), T5 (CALY still `invalid_ohlc` end-to-end), T6 (clamp counter in manifest + summary), and the VSTS-excluded / TVTX-priced end-to-end regression.
- `test_constants.py` — the calibration-guard test (`0.079 < RISK_FLOOR_ADR_RATIO < 0.256`; `0.771 < OHLC_CLAMP_MAX_PCT < 1.664`).
- `testkit.py` — extend `insert_candidate` to accept `adr_pct=None` (thread it into the INSERT).

**No production code (analysis only):**
- Task 8 — the capture-timing trace. Deliverable is a note folded into the return report (+ a gitignored scratch script). No repo file, no commit.

---

## Fixture provenance (§4 real-data mandate — how each fixture is classed)

The brief §4 mandates the DISCRIMINATING artifact-class fixtures derive from REAL emitter data. This plan classes every fixture and honors the mandate exactly:

- **Real-data discriminators (lifted verbatim from the live DB/archive 2026-07-04):** VSTS 06-25 (T1), TVTX 06-12 (T2), GTX run-89 (T3 — a real ORDINARY signal), DINO 06-18 ragged (T4), CALY 07-01 ragged (T5), and the T6/T7 seeds reuse those same real bars. These carry the adversarial guarantee: a plausibly-wrong impl (a floor that misses VSTS, over-catches TVTX, or a clamp that mis-thresholds DINO/CALY) FAILS them, because the numbers are the market's, not the test author's.
- **Legitimately synthetic scaffolds (NOT artifact discriminators):** `_min_risk_per_share`'s pure-arithmetic unit (adr 4.0 / entry 100 → a round check of the formula, no market shape involved) and the calibration-guard constants test (they assert the SHIPPED constant sits in the live-derived gap). These are unit/guard tests of pure functions; the real-data mandate does not apply and synthetic inputs are correct here.
- **Real bar embedded in a minimal signal (T4/T5 e2e):** the RAGGED BAR is real (DINO/CALY lifted verbatim); the surrounding 2-bar entry/tail is minimal scaffolding whose only job is to make the ragged bar reachable through `run_harness`. The brief explicitly asks for "real ragged bars ... lifted from the live archive" — the bar is real; the scaffold is not the thing under test.

---

## Task 1: Measurement-policy constants + calibration guard

**Files:**
- Modify: `research/harness/shadow_expectancy/constants.py`
- Test: `tests/research/shadow_expectancy/test_constants.py`

**Interfaces:**
- Produces: `RISK_FLOOR_ADR_RATIO: float`, `OHLC_CLAMP_MAX_PCT: float`, `CLAMP_SAMPLE_LIMIT: int` — consumed by Tasks 2-6.

- [ ] **Step 1: Write the failing test**

Add to `tests/research/shadow_expectancy/test_constants.py`:

```python
from research.harness.shadow_expectancy import constants as c


def test_risk_floor_adr_ratio_inside_live_derived_safe_gap():
    # Live 2026-07-04: VSTS(catch) rps/ADR = 0.0794; TVTX(survive) rps/ADR = 0.2564 (run101).
    # A value in this gap catches VSTS and spares TVTX. RD rules the exact value.
    assert 0.0794 < c.RISK_FLOOR_ADR_RATIO < 0.2564


def test_ohlc_clamp_threshold_inside_live_derived_gap():
    # Live 2026-07-04: tight cluster tops out at TLYS 0.771%; CALY outlier 1.664%.
    assert 0.771 < c.OHLC_CLAMP_MAX_PCT < 1.664


def test_clamp_sample_limit_is_a_bounded_positive_int():
    assert isinstance(c.CLAMP_SAMPLE_LIMIT, int) and 0 < c.CLAMP_SAMPLE_LIMIT <= 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/shadow_expectancy/test_constants.py -q`
Expected: FAIL with `AttributeError: module ... has no attribute 'RISK_FLOOR_ADR_RATIO'`.

- [ ] **Step 3: Write minimal implementation**

Append to `research/harness/shadow_expectancy/constants.py` (after `PRICE_TICK_DECIMALS`):

```python
# --- 19-D measurement policy (RD-RULED at plan review; values default to the recommendation) ---
# (a) Risk-unit floor: a mechanical risk-per-share below this fraction of the candidate's screening
# ADR (adr_pct) is degenerate -- a near-zero denominator inflates R without bound. Excluded as
# degenerate_risk. Discriminator: rps / (adr_pct/100 * entry_fill) < RISK_FLOOR_ADR_RATIO.
# Live calibration (2026-07-04, N=187 triggered signals): VSTS(catch)=0.0794, TVTX(survive)=0.2564;
# the safe gap is (0.0794, 0.2564). Default = moderate: catches VSTS + the tight ARMK/PGNY cluster.
# When adr_pct is null/<=0 the floor is DISABLED (graceful degrade to the old zero-floor) -- NO
# %-of-price fallback (that is the misclassifying form we reject; adr is 100%-populated in prod).
RISK_FLOOR_ADR_RATIO = 0.15
# (b) Epsilon-tolerant OHLC reader: a bar whose low sits above min(o,c) OR high below max(o,c) by
# <= this % of close is clamped (low=min(l,o,c), high=max(h,o,c)); above it stays invalid_ohlc.
# Reader-side ONLY -- the immutable log + archive are untouched. Live cluster 0.037%-0.771% (15
# bars); CALY 1.664% is the lone outlier (default leaves it excluded).
OHLC_CLAMP_MAX_PCT = 1.0
# Max per-ticker clamp samples surfaced in the artifact summary/manifest (observability cap).
CLAMP_SAMPLE_LIMIT = 20
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/research/shadow_expectancy/test_constants.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/harness/shadow_expectancy/constants.py tests/research/shadow_expectancy/test_constants.py
git commit -m "feat(shadow): 19-D Task 1 -- risk-floor + epsilon-clamp measurement-policy constants"
```

---

## Task 2: Risk-unit floor in `simulate` (T1 VSTS caught, T2 TVTX survives, T3 normal unchanged)

**Files:**
- Modify: `research/harness/shadow_expectancy/simulator.py` (`SimParams` ~15-24; `simulate` guard ~97-107)
- Test: `tests/research/shadow_expectancy/test_simulator.py`

**Interfaces:**
- Consumes: `SimParams` (existing), `Bar` (from `io`), `RISK_FLOOR_ADR_RATIO` (Task 1 — but passed via `SimParams`, so `simulate` reads no constant directly).
- Produces: `simulate(*, pivot, entry_bar, forward_bars, params, adr_pct=None)` — `adr_pct` defaults `None` so the existing `run.py` call keeps compiling until Task 3. `SimParams` gains ONE field `risk_floor_adr_ratio: float = 0.0` (default = FLOOR DISABLED, so every existing `SimParams(...)` construction and non-`run.py` test is unaffected). A module-level `_min_risk_per_share(entry_fill, adr_pct, params) -> float` that returns `0.0` when `adr_pct` is null/`<=0` (floor disabled — NO %-of-price fallback).
- **`SimResult.realized_r` is a per-ARM dict** `{"realistic": R, "favorable_reprice": R}` (or `None` when degenerate) — see `simulator.py:44`. So `on.realized_r == off.realized_r` compares the whole dict, and `on.realized_r["realistic"]` reads the realistic arm; both are the correct shape, NOT a scalar.

- [ ] **Step 1: Write the failing tests**

Add to `tests/research/shadow_expectancy/test_simulator.py` (import `SimParams`, `simulate`, `Bar` as the file already does — mirror its existing imports):

```python
from research.harness.shadow_expectancy.io import Bar
from research.harness.shadow_expectancy.simulator import SimParams, simulate


def _params(*, ratio):
    # A SimParams whose non-floor fields never fire in these 1-2-bar walks (partial at session 3,
    # be trigger 1.0, MA needs >=10 closes) -- only the floor is under test.
    return SimParams(
        initial_shares=100.0, partial_session_n=3, partial_pct=0.5,
        breakeven_r_trigger=1.0, maturity_fast_ma_r=2.0, ma_fast_period=10,
        ma_slow_period=20, horizon_sessions=126, risk_floor_adr_ratio=ratio)


# --- Real VSTS 06-25 A+ geometry (live DB 2026-07-04) ---
# pivot 13.5600004; adr_pct 4.16785698; entry bar O=13.6000004 H=14.0200005 L=13.5550003 C=13.7399998
# entry_fill = max(pivot, open) = 13.6000004; initial_stop = low = 13.5550003; rps = 0.0450001.
# min_rps @ ratio 0.15 = 0.15 * (4.16785698/100 * 13.6000004) = 0.15 * 0.5668... = 0.08502.
# PRE-FIX (ratio 0.0) -> min_rps 0.0 -> rps 0.045 > 0 -> NOT degenerate.
# POST-FIX (ratio 0.15) -> rps 0.045 < 0.08502 -> degenerate_risk.
_VSTS_ENTRY = Bar(session="2026-06-25", open=13.600000381469727, high=14.020000457763672,
                  low=13.555000305175781, close=13.739999771118164)
_VSTS_FWD = [Bar(session="2026-06-26", open=13.71, high=14.42, low=13.68, close=14.42),
             Bar(session="2026-06-29", open=14.39, high=14.85, low=14.16, close=14.83)]
_VSTS_ADR = 4.16785698182119


def test_t1_vsts_collapse_survives_zero_floor_but_caught_by_risk_floor():
    off = simulate(pivot=13.5600004, entry_bar=_VSTS_ENTRY, forward_bars=_VSTS_FWD,
                   params=_params(ratio=0.0), adr_pct=_VSTS_ADR)
    assert off.degenerate is False              # pre-fix: the zero-floor lets it through
    on = simulate(pivot=13.5600004, entry_bar=_VSTS_ENTRY, forward_bars=_VSTS_FWD,
                  params=_params(ratio=0.15), adr_pct=_VSTS_ADR)
    assert on.degenerate is True                # post-fix: caught
    assert on.exit_reason == "degenerate_risk"
    assert on.realized_r is None


# --- Real TVTX 06-12 geometry (live DB 2026-07-04) ---
# pivot 49.6800003; adr_pct 4.74395635; entry O=49.0999985 H=52.7200012 L=48.9799995 C=52.0400009
# entry_fill = max(pivot, open) = 49.6800003; initial_stop = low = 48.9799995; rps = 0.7000008.
# min_rps @ 0.15 = 0.15 * (4.74395635/100 * 49.6800003) = 0.15 * 2.3568 = 0.35352.
# rps 0.70 > 0.35352 -> SURVIVES both floor-off and floor-on -> R IDENTICAL.
_TVTX_ENTRY = Bar(session="2026-06-12", open=49.099998474121094, high=52.720001220703125,
                  low=48.97999954223633, close=52.040000915527344)
_TVTX_FWD = [Bar(session="2026-06-15", open=52.44, high=53.88, low=52.06, close=53.8),
             Bar(session="2026-06-16", open=53.88, high=54.38, low=52.72, close=53.38)]
_TVTX_ADR = 4.7439563469121495


def test_t2_tvtx_tight_but_real_survives_with_r_unchanged():
    off = simulate(pivot=49.6800003, entry_bar=_TVTX_ENTRY, forward_bars=_TVTX_FWD,
                   params=_params(ratio=0.0), adr_pct=_TVTX_ADR)
    on = simulate(pivot=49.6800003, entry_bar=_TVTX_ENTRY, forward_bars=_TVTX_FWD,
                  params=_params(ratio=0.15), adr_pct=_TVTX_ADR)
    assert on.degenerate is False                       # NOT over-caught
    assert on.realized_r is not None
    assert on.realized_r == off.realized_r              # R unchanged pre->post
    assert on.risk_per_share == off.risk_per_share


# --- Real GTX run-89 geometry (live DB 2026-07-04): an ORDINARY healthy signal (NOT an artifact) ---
# pivot 34.34; adr_pct 4.0236; entry O=33.83 H=34.42 L=33.36 C=33.56. entry_fill=max(pivot,open)=34.34;
# stop=low=33.36; rps=0.98 (2.85% of entry; rps/ADR=0.709 -- an order of magnitude above the floor).
# min_rps @ 0.15 = 0.15 * (4.0236/100 * 34.34) = 0.207; rps 0.98 >> 0.207 -> SURVIVES both paths.
_GTX_ENTRY = Bar(session="2026-06-12", open=33.83000183105469, high=34.41999816894531,
                 low=33.36000061035156, close=33.560001373291016)
_GTX_FWD = [Bar(session="2026-06-15", open=34.32, high=34.5, low=33.61, close=34.13),
            Bar(session="2026-06-16", open=34.45, high=35.055, low=34.12, close=34.61)]
_GTX_ADR = 4.0236


def test_t3_normal_signal_r_identical_pre_post():
    # Real ordinary signal: the floor must not move it. Non-vacuous -- a floor that (wrongly)
    # excluded GTX would flip degenerate to True and realized_r to None, failing these asserts.
    off = simulate(pivot=34.34, entry_bar=_GTX_ENTRY, forward_bars=_GTX_FWD,
                   params=_params(ratio=0.0), adr_pct=_GTX_ADR)
    on = simulate(pivot=34.34, entry_bar=_GTX_ENTRY, forward_bars=_GTX_FWD,
                  params=_params(ratio=0.15), adr_pct=_GTX_ADR)
    assert on.degenerate is False and on.realized_r is not None    # NOT excluded
    assert on.realized_r == off.realized_r                         # R (both arms) unchanged pre->post
    assert on.risk_per_share == off.risk_per_share


def test_min_risk_per_share_zero_when_adr_missing_else_ratio_times_adr_price():
    from research.harness.shadow_expectancy.simulator import _min_risk_per_share
    p = _params(ratio=0.15)
    # adr null/<=0 -> floor DISABLED -> 0.0 (graceful degrade; no %-of-price fallback).
    assert _min_risk_per_share(100.0, None, p) == 0.0
    assert _min_risk_per_share(100.0, 0.0, p) == 0.0
    # adr present -> ratio * adr_price. adr 4.0% of 100 = 4.0; * 0.15 = 0.6.
    assert abs(_min_risk_per_share(100.0, 4.0, p) - 0.6) < 1e-9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/research/shadow_expectancy/test_simulator.py -k "t1_vsts or t2_tvtx or t3_normal or min_risk" -q`
Expected: FAIL — `SimParams.__init__() got an unexpected keyword argument 'risk_floor_adr_ratio'` (and `_min_risk_per_share` not importable).

- [ ] **Step 3: Write minimal implementation**

In `research/harness/shadow_expectancy/simulator.py`, extend `SimParams` (append the ONE field WITH a default so every existing construction stays valid):

```python
@dataclass(frozen=True)
class SimParams:
    initial_shares: float
    partial_session_n: int
    partial_pct: float
    breakeven_r_trigger: float
    maturity_fast_ma_r: float
    ma_fast_period: int
    ma_slow_period: int
    horizon_sessions: int
    # 19-D risk-unit floor (default 0.0 = DISABLED, so pre-19-D constructions are unaffected).
    risk_floor_adr_ratio: float = 0.0
```

Add the helper (module level, near `_entry_fill`):

```python
def _min_risk_per_share(entry_fill: float, adr_pct, params: SimParams) -> float:
    """19-D: the minimum plausible risk-per-share. When the candidate's screening ADR is present,
    the floor is a fraction of the ADR expressed in price (ratio * adr_pct/100 * entry_fill); a
    near-zero rps below it is a degenerate denominator (R inflates without bound). When adr_pct is
    null/<=0 (schema-nullable; 0% of the live corpus) the floor is DISABLED -> return 0.0 (graceful
    degrade to the old zero-floor; NO %-of-price fallback -- that is the misclassifying form we
    reject). Returns 0.0 when risk_floor_adr_ratio is 0.0 (floor disabled) too."""
    if adr_pct is not None and adr_pct > 0:
        adr_price = (adr_pct / 100.0) * entry_fill
        return params.risk_floor_adr_ratio * adr_price
    return 0.0
```

Change the `simulate` signature and the degenerate guard (lines ~97-107):

```python
def simulate(*, pivot, entry_bar: Bar, forward_bars, params: SimParams, adr_pct=None):
    # C1 / spec 5.2 / D6: mechanical stop = entry_bar.low (derived, not candidate-supplied).
    entry_fill = _entry_fill(pivot, entry_bar)
    initial_stop = entry_bar.low
    rps = initial_risk_per_share(entry_price=entry_fill, initial_stop=initial_stop)
    ambiguous = entry_bar.low < entry_fill
    # 19-D: the risk floor SUBSUMES the old zero-floor (min_rps >= 0). rps <= 0 stays caught.
    min_rps = _min_risk_per_share(entry_fill, adr_pct, params)
    if rps <= 0 or rps < min_rps:
        return SimResult(entry_fill=entry_fill, initial_stop=initial_stop,
                         risk_per_share=rps, entry_bar_ambiguous=ambiguous,
                         degenerate=True, exit_reason="degenerate_risk",
                         open_at_horizon=False, realized_r=None)
```

**IF RD RULES WINSORIZE INSTEAD OF EXCLUDE** (variant — do NOT ship both): replace the guard with:

```python
    min_rps = _min_risk_per_share(entry_fill, adr_pct, params)
    if rps <= 0:   # a truly non-positive denominator is still unrecoverable -> exclude
        return SimResult(..., degenerate=True, exit_reason="degenerate_risk", ...)
    rps = max(rps, min_rps)   # winsorize the denominator; the signal is retained and priced
```
(then T1 asserts VSTS's R is *capped* at `(mark - entry_fill)/min_rps` rather than excluded — see the §"Exclusion vs winsorize" arithmetic; T2/T3 unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/research/shadow_expectancy/test_simulator.py -q`
Expected: PASS (the new tests plus every pre-existing simulator test — the defaulted `SimParams` fields keep them green).

- [ ] **Step 5: Commit**

```bash
git add research/harness/shadow_expectancy/simulator.py tests/research/shadow_expectancy/test_simulator.py
git commit -m "feat(shadow): 19-D Task 2 -- risk-unit floor in simulate (VSTS caught, TVTX/normal unchanged)"
```

---

## Task 3: Wire `adr_pct` + floor constants through `run.py`

**Files:**
- Modify: `research/harness/shadow_expectancy/run.py` (`params = SimParams(...)` ~80-84; the `simulate(...)` call ~181-182)
- Test: `tests/research/shadow_expectancy/test_run.py` + `testkit.py`

**Interfaces:**
- Consumes: `simulate(..., adr_pct=...)` and the `SimParams.risk_floor_adr_ratio` field (Task 2); `RISK_FLOOR_ADR_RATIO` (Task 1); `candidate.adr_pct` (already on the `Candidate` model, resolved by `io.resolve_candidate`).
- Produces: production `run_harness` now applies the risk floor. `testkit.insert_candidate` gains `adr_pct=None`.

- [ ] **Step 1: Write the failing test**

Extend `testkit.insert_candidate` first (needed by the test): add an `adr_pct=None` kwarg and include it in the INSERT column list:

```python
def insert_candidate(conn, *, ticker, bucket, pivot, initial_stop, close=None,
                     criteria=(), adr_pct=None):
    ...
    cur = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, pivot,"
        " initial_stop, adr_pct, rs_method) VALUES (?,?,?,?,?,?,?,?)",
        (eval_id, ticker, bucket, close, pivot, initial_stop, adr_pct, "fallback_spy"),
    )
```

Add to `tests/research/shadow_expectancy/test_run.py` (mirror the file's existing `run_harness` + seeding style; use `testkit` helpers):

```python
def test_run_harness_applies_risk_floor_excludes_collapsed_signal(tmp_path):
    # A real-VSTS-shaped collapsed signal through the full harness: rps 0.045 on adr 4.168%.
    from tests.research.shadow_expectancy.testkit import (
        insert_candidate, insert_pipeline_run, insert_detection, insert_observation, make_db)
    import json
    from pathlib import Path
    from research.harness.shadow_expectancy.run import run_harness
    conn = make_db(tmp_path)
    eval_id = insert_candidate(conn, ticker="VSTS", bucket="watch", pivot=13.56,
                               initial_stop=11.62, close=13.49, adr_pct=4.16785698,
                               criteria=[("proximity_20ma", "trend_template", "fail")])
    pr = insert_pipeline_run(conn, eval_id)
    det = insert_detection(conn, ticker="VSTS", pipeline_run_id=pr, pivot=13.56,
                           data_asof_date="2026-06-24", detection_date="2026-06-25")
    insert_observation(conn, det, "2026-06-25", o=13.60, h=14.02, l=13.555, c=13.74,
                       status="triggered_open", event="entry_fired")
    insert_observation(conn, det, "2026-06-26", o=13.71, h=14.42, l=13.68, c=14.42,
                       status="triggered_open")
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=tmp_path / "out",
                                    source="pipeline")
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    h = f["per_hypothesis"]["Near-A+ defensible: extension test"]
    assert h["excluded"].get("degenerate_risk", 0) == 1   # collapsed -> excluded
    assert h["open_at_horizon"] == 0 and h["closed"] == 0


def test_run_harness_legacy_shape_stays_priced_null_adr_disables_floor(tmp_path):
    # MECHANIZED null-adr blast-radius guard (Codex R1/R2/R3): the canonical legacy fixture shape
    # (pivot 10, entry L=9.6 -> rps 0.4) carries adr_pct=None (omitted). Null adr DISABLES the floor
    # (min_rps=0.0 -> old zero-floor), so the signal behaves EXACTLY as pre-19-D and MUST stay
    # PRICED, never degenerate_risk. This locks the "null-adr disables the floor" contract in code:
    # any regression that made a null-adr signal degenerate would flip this and FAIL here.
    from tests.research.shadow_expectancy.testkit import (
        insert_candidate, insert_pipeline_run, insert_detection, insert_observation, make_db)
    import json
    from pathlib import Path
    from research.harness.shadow_expectancy.run import run_harness
    conn = make_db(tmp_path)
    eval_id = insert_candidate(conn, ticker="LEG", bucket="watch", pivot=10.0,
                               initial_stop=9.0, close=10.2,   # adr_pct omitted -> None -> fallback
                               criteria=[("proximity_20ma", "trend_template", "fail")])
    pr = insert_pipeline_run(conn, eval_id)
    det = insert_detection(conn, ticker="LEG", pipeline_run_id=pr, pivot=10.0,
                           data_asof_date="2026-05-31", detection_date="2026-06-01")
    insert_observation(conn, det, "2026-06-01", o=10.0, h=10.4, l=9.6, c=10.2,
                       status="triggered_open")           # entry: rps = 10.0 - 9.6 = 0.4 (4%)
    insert_observation(conn, det, "2026-06-02", o=10.3, h=10.6, l=10.1, c=10.5,
                       status="triggered_open")           # no stop (low 10.1 > 9.6) -> priced
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=tmp_path / "out",
                                    source="pipeline", horizon_sessions=2)
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    h = f["per_hypothesis"]["Near-A+ defensible: extension test"]
    assert h["excluded"].get("degenerate_risk", 0) == 0   # the fallback does NOT catch a 4% stop
    assert h["open_at_horizon"] + h["closed"] >= 1        # stays priced
```

(Note: the watch bucket + `proximity_20ma` miss attributes to H2 "Near-A+ defensible: extension test", matching the existing `test_real_shapes.py` fixtures. Verify the live hypothesis name in `swing/data/repos/hypothesis.py` seed / the existing test if it differs.)

- [ ] **Step 2: Run tests to verify the exclusion one fails**

Run: `python -m pytest tests/research/shadow_expectancy/test_run.py -k "risk_floor or null_adr" -q`
Expected: `test_run_harness_applies_risk_floor_excludes_collapsed_signal` FAILs — the signal is `open_at_horizon` (or priced), NOT excluded, because `run.py` does not yet set the floor. `test_run_harness_legacy_shape_stays_priced_null_adr_disables_floor` is a standing-green REGRESSION LOCK (a null-adr signal is priced whether or not the floor is active); it passes both pre- and post-fix by design — its job is to FAIL only if a later change makes a null-adr signal degenerate.

- [ ] **Step 3: Write minimal implementation**

In `run.py`, set the `SimParams.risk_floor_adr_ratio` field from the constant:

```python
    params = SimParams(
        initial_shares=c.INITIAL_SHARES, partial_session_n=partial_session_n,
        partial_pct=c.PARTIAL_PCT, breakeven_r_trigger=breakeven_r,
        maturity_fast_ma_r=c.MATURITY_FAST_MA_R, ma_fast_period=c.MA_FAST_PERIOD,
        ma_slow_period=c.MA_SLOW_PERIOD, horizon_sessions=horizon_sessions,
        risk_floor_adr_ratio=c.RISK_FLOOR_ADR_RATIO)
```

And pass `adr_pct` into the `simulate` call (~181):

```python
        sim = simulate(pivot=candidate.pivot, entry_bar=entry_bar,
                       forward_bars=forward_bars, params=params,
                       adr_pct=candidate.adr_pct)
```

- [ ] **Step 4: Run test to verify it passes; then run the WHOLE shadow suite**

Run: `python -m pytest tests/research/shadow_expectancy/ -q`
Expected: PASS.

**Null-adr blast-radius — STRUCTURALLY zero (the Codex R1/R2/R3 finding, resolved by design).** `testkit.insert_candidate` leaves `adr_pct=None`, so EVERY pre-existing `run_harness` fixture has null adr. Because null/`<=0` adr **DISABLES** the floor (`_min_risk_per_share` returns `0.0` → the old zero-floor), every legacy fixture behaves EXACTLY as pre-19-D — there is no %-of-price fallback to trip. This is the structural fix (Codex R3's preferred "truly disabled fallback on legacy paths"): the blast radius is zero by construction, not by an unproven claim. The mechanized `test_run_harness_legacy_shape_stays_priced_null_adr_disables_floor` (Step 1) locks it. Still confirm the full suite is green (the recipe §2 cross-cutting net); if any pre-existing fixture DID set a non-null `adr_pct` with a sub-floor rps (none does today), RAISE its rps or adjust its `adr_pct` — never weaken the floor for a synthetic fixture.

- [ ] **Step 5: Commit**

```bash
git add research/harness/shadow_expectancy/run.py tests/research/shadow_expectancy/test_run.py tests/research/shadow_expectancy/testkit.py
git commit -m "feat(shadow): 19-D Task 3 -- wire candidate.adr_pct + floor constants through run_harness"
```

---

## Task 4: `clamp_ragged_bars` reader-clamp (T4-math, T5-math, passthrough, idempotence)

**Files:**
- Modify: `research/harness/shadow_expectancy/validate.py`
- Test: `tests/research/shadow_expectancy/test_validate.py`

**Interfaces:**
- Consumes: `Bar` (from `io`), `_finite_nonneg` (existing in `validate.py`).
- Produces:
  - `@dataclass(frozen=True) class ClampEvent: session: str; clamp_pct: float`
  - `_shape_violation_pct(b: Bar) -> float | None` — the clamp magnitude as % of close (`None` when price unmeasurable; `0.0` when no shape violation).
  - `clamp_ragged_bars(bars, *, max_pct) -> tuple[list[Bar], list[ClampEvent]]` — widens sub-threshold shape violations; leaves non-finite, above-threshold, and non-violating bars UNCHANGED.

- [ ] **Step 1: Write the failing tests**

Add to `tests/research/shadow_expectancy/test_validate.py`:

```python
from dataclasses import replace

from research.harness.shadow_expectancy.io import Bar
from research.harness.shadow_expectancy.validate import (
    clamp_ragged_bars, validate_bars, _shape_violation_pct,
)

# Real DINO 06-18 (live archive): high 65.51 < max(o,c)=65.78 -> hi_delta 0.27; 0.27/64.50 = 0.4186%.
_DINO = Bar(session="2026-06-18", open=65.78, high=65.51, low=63.85, close=64.50)
# Real CALY 07-01 (live archive): low 18.4001 > min(o,c)=18.09 -> lo_delta 0.3101; /18.64 = 1.6636%.
_CALY = Bar(session="2026-07-01", open=18.09, high=18.99, low=18.4001, close=18.64)
_CLEAN = Bar(session="2026-06-19", open=64.6, high=66.0, low=64.4, close=65.8)


def test_shape_violation_pct_matches_live_magnitudes():
    assert abs(_shape_violation_pct(_DINO) - 0.4186) < 0.001
    assert abs(_shape_violation_pct(_CALY) - 1.6636) < 0.001
    assert _shape_violation_pct(_CLEAN) == 0.0


def test_t4_math_dino_class_clamped_at_1pct_recovers_bar():
    # PRE-FIX (max_pct 0.0): 0.4186 > 0 -> NOT clamped -> validate_bars rejects it.
    off, ev_off = clamp_ragged_bars([_DINO], max_pct=0.0)
    assert off == [_DINO] and ev_off == []
    assert validate_bars(off) == "invalid_ohlc"
    # POST-FIX (max_pct 1.0): clamped high -> 65.78; now valid.
    on, ev_on = clamp_ragged_bars([_DINO], max_pct=1.0)
    assert on[0].high == 65.78 and on[0].low == 63.85    # only high widened
    assert validate_bars(on) is None
    assert len(ev_on) == 1 and ev_on[0].session == "2026-06-18"


def test_t5_math_caly_class_not_clamped_at_1pct_but_clamped_at_2pct():
    # At the production 1.0% threshold CALY stays invalid under BOTH the clamp and validate.
    on, ev = clamp_ragged_bars([_CALY], max_pct=1.0)
    assert on == [_CALY] and ev == []
    assert validate_bars(on) == "invalid_ohlc"
    # The fixture is NOT trivially always-invalid: at 2.0% it clamps + recovers (boundary is real).
    up, ev2 = clamp_ragged_bars([_CALY], max_pct=2.0)
    assert up[0].low == 18.09 and up[0].high == 18.99    # only low widened
    assert validate_bars(up) is None and len(ev2) == 1


def test_clamp_leaves_non_finite_bar_untouched():
    nan_bar = Bar(session="d", open=float("nan"), high=1.0, low=0.5, close=0.9)
    out, ev = clamp_ragged_bars([nan_bar], max_pct=1.0)
    assert out == [nan_bar] and ev == []                 # cannot widen a NaN -> passthrough
    assert validate_bars(out) == "invalid_ohlc"


def test_clamp_is_idempotent_and_never_creates_high_below_low():
    once, _ = clamp_ragged_bars([_DINO], max_pct=1.0)
    twice, ev2 = clamp_ragged_bars(once, max_pct=1.0)
    assert twice == once and ev2 == []                   # already clamped -> no-op
    assert twice[0].high >= twice[0].low
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/research/shadow_expectancy/test_validate.py -k "clamp or shape or t4_math or t5_math" -q`
Expected: FAIL — `ImportError: cannot import name 'clamp_ragged_bars'`.

- [ ] **Step 3: Write minimal implementation**

In `research/harness/shadow_expectancy/validate.py`, add (below `validate_bars`, reusing `_finite_nonneg`):

```python
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class ClampEvent:
    session: str
    clamp_pct: float


def _shape_violation_pct(b: Bar) -> float | None:
    """The clamp magnitude of a bar's OHLC shape violation, as % of CLOSE (spec brief 2b -- the
    threshold is measured against close, faithfully, with NO other-price fallback). Returns 0.0
    when the bar is well-formed (low<=min(o,c) and high>=max(o,c)); None when close<=0 (the
    magnitude is undefined as a %-of-close, so the bar is not clampable and is left for
    validate_bars to route)."""
    if b.close <= 0:
        return None
    lo_delta = max(0.0, b.low - min(b.open, b.close))    # low sitting ABOVE the body
    hi_delta = max(0.0, max(b.open, b.close) - b.high)   # high sitting BELOW the body
    return 100.0 * max(lo_delta, hi_delta) / b.close


def clamp_ragged_bars(bars, *, max_pct):
    """19-D epsilon-tolerant reader (spec brief 2b). Reader-side ONLY -- the immutable log + the
    OHLCV archive are untouched. For each bar with a shape violation (low>min(o,c) OR high<max(o,c))
    whose magnitude is <= max_pct% of close, WIDEN the bar: high=max(h,o,c), low=min(l,o,c). Above
    max_pct -> left UNCHANGED (validate_bars then routes it to invalid_ohlc, exactly as today).
    Non-finite/negative bars are NOT clampable -> passthrough. Widening only ever grows the range,
    so it is idempotent and can never create high<low. Returns (clamped_bars, clamp_events)."""
    out = []
    events = []
    for b in bars:
        if not _finite_nonneg(b.open, b.high, b.low, b.close):
            out.append(b)
            continue
        pct = _shape_violation_pct(b)
        if pct is None or pct == 0.0 or pct > max_pct:
            out.append(b)
            continue
        out.append(replace(b, high=max(b.high, b.open, b.close),
                           low=min(b.low, b.open, b.close)))
        events.append(ClampEvent(session=b.session, clamp_pct=pct))
    return out, events
```

(The existing top-of-file `import math` and the `_finite_nonneg` helper stay. Add `from dataclasses import dataclass, replace` to the imports.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/research/shadow_expectancy/test_validate.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/harness/shadow_expectancy/validate.py tests/research/shadow_expectancy/test_validate.py
git commit -m "feat(shadow): 19-D Task 4 -- epsilon-tolerant clamp_ragged_bars reader (DINO recovered, CALY held)"
```

---

## Task 5: Wire the clamp into `run.py` before `validate_signal` (T4 recovered, T5 held, end-to-end)

**Files:**
- Modify: `research/harness/shadow_expectancy/run.py` (after the `missing_observations` guard ~139-142, before `validate_signal` ~147)
- Test: `tests/research/shadow_expectancy/test_real_shapes.py`

**Interfaces:**
- Consumes: `clamp_ragged_bars` (Task 4); `OHLC_CLAMP_MAX_PCT` (Task 1).
- Produces: `run_harness` clamps each canonical chain's `all_bars` before validation; accumulates a `(ticker, session) -> clamp_pct` dict named `clamped_bars` (DISTINCT bars, deduped — `session` IS `observation_date`, so a ticker with ragged bars on 2 dates counts as 2), PLUS a `clamped_events_total` int (every clamp operation across all canonical chains — signal-weighted inflow, so a bar recurring across N signals/runs is NOT hidden). Both consumed by Task 6.

**Control-flow ordering PROOF (pinned against `run.py` on disk 2026-07-04 — re-ground line numbers before editing).** The clamp MUST land after collapse and before validation. The current per-group control flow is:
1. `res = collapse_detections(views)` — `run.py:~101` (collapse; excludes `inconsistent_detection_series`).
2. `candidate = io.resolve_candidate(...)` — `~109`.
3. `hyps = attribute_hypotheses(...)` — `~116`.
4. `canonical_chain = chains[res.canonical.detection_id]` + `all_bars = [io.parse_bar(...) ...]` — `~127-130`.
5. `if not all_bars: ... missing_observations` guard — `~139-142`.
6. **← INSERT `clamp_ragged_bars(all_bars, ...)` HERE (~145)** — after the guard (nothing to clamp on an empty chain), before validation.
7. `reason = validate_signal(pivot=..., bars=all_bars)` — `~147`.
8. `entry_idx = next(... b.high >= candidate.pivot ...)` — `~154`; `simulate(...)` — `~181`.
So the clamp (step 6) is strictly AFTER collapse (step 1) and BEFORE validate/entry/simulate (steps 7-8). **Dedup is unaffected:** `collapse_detections` compares each chain's `_series_key` = `_ohlc_tuple(o.ohlc_today_json)` (raw JSON, `run.py:~40-41`/`~100`), NOT `parse_bar`/clamp output — collapse operates on verbatim log OHLC, so widening bars post-collapse cannot change which chain is canonical or which duplicates collapse (the reader-side-only lock).

- [ ] **Step 1: Write the failing tests**

Add to `tests/research/shadow_expectancy/test_real_shapes.py` (reuse the file's `testkit` imports + `_assert_no_look_ahead`):

```python
def _seed_signal_with_walk_bar(conn, *, ticker, pivot, adr, entry, walk, tail):
    eval_id = insert_candidate(conn, ticker=ticker, bucket="watch", pivot=pivot,
                               initial_stop=pivot - 5, close=pivot, adr_pct=adr,
                               criteria=[("proximity_20ma", "trend_template", "fail")])
    pr = insert_pipeline_run(conn, eval_id)
    det = insert_detection(conn, ticker=ticker, pipeline_run_id=pr, pivot=pivot,
                           data_asof_date="2026-06-16", detection_date="2026-06-17")
    for (d, o, h, low, cl) in (entry, walk, tail):
        insert_observation(conn, det, d, o=o, h=h, l=low, c=cl, status="triggered_open")
    conn.commit()


def test_t4_dino_class_ragged_walk_bar_recovered_end_to_end(tmp_path):
    # entry clean (rps 2.0 clears the floor); walk = real DINO 06-18 ragged (0.42% <= 1.0%);
    # tail clean. PRE-FIX: whole signal invalid_ohlc. POST-FIX: clamped -> priced (open at horizon).
    conn = make_db(tmp_path)
    _seed_signal_with_walk_bar(
        conn, ticker="DINO", pivot=64.0, adr=3.0,
        entry=("2026-06-17", 65.0, 66.0, 63.0, 65.5),
        walk=("2026-06-18", 65.78, 65.51, 63.85, 64.50),     # real ragged bar
        tail=("2026-06-19", 64.6, 66.0, 64.4, 65.8))
    _assert_no_look_ahead(conn)
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=tmp_path / "out",
                                    source="pipeline", horizon_sessions=2)
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    h = f["per_hypothesis"]["Near-A+ defensible: extension test"]
    assert h["excluded"].get("invalid_ohlc", 0) == 0     # NOT lost to the ragged bar
    assert h["open_at_horizon"] == 1                      # recovered + priced
    # rps 2.0 -> open MTM R = (65.8-65.0)/2.0 = 0.40 (hand-computed).


def test_t5_caly_class_above_threshold_still_invalid_end_to_end(tmp_path):
    conn = make_db(tmp_path)
    _seed_signal_with_walk_bar(
        conn, ticker="CALY", pivot=18.0, adr=5.0,
        entry=("2026-06-30", 18.0, 18.5, 17.5, 18.2),
        walk=("2026-07-01", 18.09, 18.99, 18.4001, 18.64),   # real CALY ragged (1.66% > 1.0%)
        tail=("2026-07-02", 18.6, 19.0, 18.4, 18.8))
    _assert_no_look_ahead(conn)
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=tmp_path / "out",
                                    source="pipeline", horizon_sessions=2)
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    h = f["per_hypothesis"]["Near-A+ defensible: extension test"]
    assert h["excluded"].get("invalid_ohlc", 0) == 1     # above threshold -> still excluded
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/research/shadow_expectancy/test_real_shapes.py -k "t4_dino or t5_caly" -q`
Expected: T4 FAILs (signal excluded `invalid_ohlc`, not recovered); T5 PASSES already (both pre/post exclude CALY) — acceptable, T5 is a lock that must hold across the change.

- [ ] **Step 3: Write minimal implementation**

In `run.py`, add the import at the top with the other harness imports:

```python
from research.harness.shadow_expectancy.validate import clamp_ragged_bars, validate_signal
```

Initialise the accumulators before the group loop (near `results_rows = []`, ~78):

```python
    clamped_bars: dict[tuple, float] = {}   # (ticker, session) -> clamp_pct (DISTINCT clamped bars)
    clamped_events_total = 0                # every clamp operation (signal-weighted inflow)
```

Insert the clamp between the `missing_observations` guard and `validate_signal` (after line ~142, before ~147):

```python
        # 19-D reader-side epsilon clamp (brief 2b): widen sub-threshold OHLC shape violations
        # BEFORE validation so a sub-cent ragged bar no longer excludes the whole signal. The
        # immutable log is untouched -- this mutates only the in-memory canonical chain. Applied
        # AFTER collapse (collapse compares verbatim log OHLC), so dedup is unaffected.
        all_bars, clamp_events = clamp_ragged_bars(all_bars, max_pct=c.OHLC_CLAMP_MAX_PCT)
        clamped_events_total += len(clamp_events)          # signal-weighted (not deduped)
        for ev in clamp_events:
            clamped_bars.setdefault((ticker, ev.session), ev.clamp_pct)   # distinct bar
```

- [ ] **Step 4: Run tests to verify they pass; then the whole shadow suite**

Run: `python -m pytest tests/research/shadow_expectancy/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/harness/shadow_expectancy/run.py tests/research/shadow_expectancy/test_real_shapes.py
git commit -m "feat(shadow): 19-D Task 5 -- wire epsilon clamp into run_harness before validate_signal"
```

---

## Task 6: Clamped-bar counter observability in manifest + summary (T6)

**Files:**
- Modify: `research/harness/shadow_expectancy/run.py` (manifest payload ~248-255; `_summary_lines` ~260-302)
- Test: `tests/research/shadow_expectancy/test_real_shapes.py`

**Interfaces:**
- Consumes: `clamped_bars` dict (Task 5); `CLAMP_SAMPLE_LIMIT` (Task 1).
- Produces: `manifest.json` gains `"ohlc_clamp": {"clamped_bar_count": int, "max_pct_threshold": float, "samples": [{"ticker", "session", "clamp_pct"}...]}`; `summary.md` gains an `## OHLC epsilon-clamp` section. `_summary_lines(funnel, scorecard, clamp_summary)` gains the third arg.

- [ ] **Step 1: Write the failing test**

Add to `tests/research/shadow_expectancy/test_real_shapes.py`:

```python
def test_t6_clamp_counter_in_manifest_and_summary(tmp_path):
    conn = make_db(tmp_path)
    _seed_signal_with_walk_bar(
        conn, ticker="DINO", pivot=64.0, adr=3.0,
        entry=("2026-06-17", 65.0, 66.0, 63.0, 65.5),
        walk=("2026-06-18", 65.78, 65.51, 63.85, 64.50),
        tail=("2026-06-19", 64.6, 66.0, 64.4, 65.8))
    _, _, summary, manifest = run_harness(db_path=tmp_path / "t.db",
                                          output_dir=tmp_path / "out",
                                          source="pipeline", horizon_sessions=2)
    m = json.loads(Path(manifest).read_text(encoding="utf-8"))
    oc = m["ohlc_clamp"]
    assert oc["clamped_bar_count"] == 1      # one distinct (ticker, session) bar
    assert oc["clamped_bar_events"] == 1     # one clamp operation (single signal here)
    assert oc["max_pct_threshold"] == 1.0
    assert oc["samples"][0]["ticker"] == "DINO"
    assert oc["samples"][0]["session"] == "2026-06-18"
    assert abs(oc["samples"][0]["clamp_pct"] - 0.4186) < 0.001
    text = Path(summary).read_text(encoding="utf-8")
    assert "OHLC epsilon-clamp" in text
    assert "clamped_bar_count=1" in text
    assert "clamped_bar_events=1" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/shadow_expectancy/test_real_shapes.py -k t6_clamp -q`
Expected: FAIL — `KeyError: 'ohlc_clamp'`.

- [ ] **Step 3: Write minimal implementation**

In `run.py`, build the summary dict after the group loop (before the artifact writes ~241):

```python
    clamp_summary = {
        "clamped_bar_count": len(clamped_bars),        # DISTINCT (ticker, session) bars
        "clamped_bar_events": clamped_events_total,     # signal-weighted operations (not deduped)
        "max_pct_threshold": c.OHLC_CLAMP_MAX_PCT,
        "samples": [{"ticker": t, "session": s, "clamp_pct": round(p, 4)}
                    for (t, s), p in sorted(clamped_bars.items())][:c.CLAMP_SAMPLE_LIMIT],
    }
```

Pass it into `_summary_lines` and the manifest payload:

```python
    output.write_summary_md(_summary_lines(funnel, scorecard, clamp_summary), summary_path)
    output.write_manifest_json({
        "harness_version": c.HARNESS_VERSION, "source": source,
        "params": {...},                       # unchanged
        "funnel": funnel, "scorecard": scorecard,
        "ohlc_clamp": clamp_summary,
        "started_iso_utc": iso, "l2_lock_preserved": True,
    }, manifest_path)
```

Extend `_summary_lines(funnel, scorecard, clamp_summary)` — add the section after the unattributed block (before the per-hypothesis loop):

```python
def _summary_lines(funnel, scorecard, clamp_summary) -> list[str]:
    ...
    lines.append("")
    lines.append("## OHLC epsilon-clamp (reader-side; log untouched; brief 2b)")
    lines.append(f"  clamped_bar_count={clamp_summary['clamped_bar_count']} "
                 f"clamped_bar_events={clamp_summary['clamped_bar_events']} "
                 f"(<= {clamp_summary['max_pct_threshold']}% shape tolerance)")
    for s in clamp_summary["samples"]:
        lines.append(f"    {s['ticker']} {s['session']} clamp={s['clamp_pct']:.4f}%")
    lines.append("")
    ...
```

(Update the other `_summary_lines(...)` call sites and any test calling it directly to pass the third arg; grep `_summary_lines` to confirm there is only the one production call.)

- [ ] **Step 4: Run test to verify it passes; then the whole shadow suite**

Run: `python -m pytest tests/research/shadow_expectancy/ -q`
Expected: PASS. Verify `test_output.py` / `test_l2_lock.py` still green (`l2_lock_preserved` unchanged; ASCII-only summary preserved — `%` and digits are ASCII).

- [ ] **Step 5: Commit**

```bash
git add research/harness/shadow_expectancy/run.py tests/research/shadow_expectancy/test_real_shapes.py
git commit -m "feat(shadow): 19-D Task 6 -- clamped-bar counter in manifest + summary"
```

---

## Task 7: End-to-end real-shape regression (VSTS excluded, TVTX priced, in one corpus)

**Files:**
- Test: `tests/research/shadow_expectancy/test_real_shapes.py`

**Interfaces:**
- Consumes: the full `run_harness` after Tasks 1-6.
- Produces: a single end-to-end guard that VSTS (A+ collapsed) is excluded `degenerate_risk` AND TVTX (tight-but-real) is priced with a nonzero R, in one seeded corpus — the binding distinction, proven through the production artifact path (not just the unit seam).

- [ ] **Step 1: Write the failing test** (it passes once Tasks 1-6 land; this is the integration lock)

```python
def test_binding_distinction_vsts_excluded_tvtx_priced_end_to_end(tmp_path):
    conn = make_db(tmp_path)
    # VSTS collapsed (watch bucket to attribute to H2), real geometry.
    ev1 = insert_candidate(conn, ticker="VSTS", bucket="watch", pivot=13.56, initial_stop=11.62,
                           close=13.49, adr_pct=4.16785698,
                           criteria=[("proximity_20ma", "trend_template", "fail")])
    pr1 = insert_pipeline_run(conn, ev1)
    d1 = insert_detection(conn, ticker="VSTS", pipeline_run_id=pr1, pivot=13.56,
                          data_asof_date="2026-06-24", detection_date="2026-06-25")
    insert_observation(conn, d1, "2026-06-25", o=13.60, h=14.02, l=13.555, c=13.74,
                       status="triggered_open")
    insert_observation(conn, d1, "2026-06-26", o=13.71, h=14.42, l=13.68, c=14.42,
                       status="triggered_open")
    # TVTX tight-but-real, real geometry.
    ev2 = insert_candidate(conn, ticker="TVTX", bucket="watch", pivot=49.68, initial_stop=41.32,
                           close=48.91, adr_pct=4.74395635,
                           criteria=[("proximity_20ma", "trend_template", "fail")])
    pr2 = insert_pipeline_run(conn, ev2)
    d2 = insert_detection(conn, ticker="TVTX", pipeline_run_id=pr2, pivot=49.68,
                          data_asof_date="2026-06-11", detection_date="2026-06-12")
    insert_observation(conn, d2, "2026-06-12", o=49.10, h=52.72, l=48.98, c=52.04,
                       status="triggered_open")
    insert_observation(conn, d2, "2026-06-15", o=52.44, h=53.88, l=52.06, c=53.8,
                       status="triggered_open")
    results, _, _, manifest = run_harness(db_path=tmp_path / "t.db",
                                          output_dir=tmp_path / "out", source="pipeline")
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    h = f["per_hypothesis"]["Near-A+ defensible: extension test"]
    assert h["excluded"].get("degenerate_risk", 0) == 1   # VSTS collapsed -> excluded
    rows = Path(results).read_text(encoding="utf-8").splitlines()[1:]
    tvtx = [r for r in rows if r.startswith("TVTX,")]
    assert len(tvtx) == 1                                  # TVTX priced (survives the floor)
    assert "VSTS" not in Path(results).read_text(encoding="utf-8")  # excluded -> no result row
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/research/shadow_expectancy/test_real_shapes.py -k binding_distinction -q`
Expected: PASS (Tasks 1-6 already deliver the behavior; this locks the integration).

- [ ] **Step 3: (no implementation — integration lock only)**
- [ ] **Step 4: (covered by Step 2)**
- [ ] **Step 5: Commit**

```bash
git add tests/research/shadow_expectancy/test_real_shapes.py
git commit -m "test(shadow): 19-D Task 7 -- end-to-end binding-distinction lock (VSTS excluded, TVTX priced)"
```

---

## Task 8: Capture-timing trace (ANALYSIS ONLY — no production code, no commit)

**Files:** none in the repo. A gitignored scratch script + a trace note folded into the return report.

**Deliverable:** a short trace note answering brief §2(c): do the ragged-bar dates correlate with capture/write timing, and do the Schwab-side rejections corroborate? If the data cannot discriminate, say so plainly — do not force a conclusion.

- [ ] **Step 1: Reproduce the ragged-bar capture-timing scan** (read-only; run a Python scratch script from `~/swing-data` with `sqlite3.connect('file:swing.db?mode=ro', uri=True)`). Fetch the rows, then in Python parse each `ohlc_today_json`, flag `low > min(o,c) or high < max(o,c)`, dedup distinct `(ticker, observation_date)`, and record `provider` (from the JSON) + the first `created_at`:

  ```sql
  SELECT o.detection_id, o.observation_date, o.ohlc_today_json, o.created_at, e.ticker
  FROM pattern_forward_observations o
  JOIN pattern_detection_events e ON e.detection_id = o.detection_id
  WHERE e.source = 'pipeline';
  ```
  Then bucket the distinct ragged bars by `observation_date` (count per session) and by `provider`. Preliminary finding (2026-07-04): all 16 distinct ragged bars are `provider=yfinance`, captured same-evening HST (`created_at` ~6h post-close, e.g. CALY 07-01 at 07-02T02:00Z = 07-01 16:00 HST), clustering on session dates with a 07-01 burst (7 of 16). Confirm this still holds on the current corpus.
- [ ] **Step 2: Fold in the Schwab-side rejections** — the cross-vendor corroboration:

  ```sql
  SELECT call_id, pipeline_run_id, endpoint, error_message, ts
  FROM schwab_api_calls
  WHERE error_message LIKE '%OHLC consistency%'
  ORDER BY call_id;
  ```
  Note the run ids, dates, and count. Preliminary: 9 `marketdata.pricehistory` "OhlcvBar invariant violated" rejections on runs 121 + 123 (2026-07-03) — the phenomenon is cross-vendor (Schwab rejects at the 18-B ladder ingest barrier while yfinance's ragged bars reach the forward-observation log).
- [ ] **Step 3: Adjudicate discriminability** — the created_at times are ~6h post-close (not "same-second"), so "later capture avoids it" is NOT clearly supported by this data; the single-session 07-01 multi-ticker burst points at provider-side consolidation lag rather than our capture instant. State this honestly; flag the residual (does the inflow shrink if capture moves later — a question for 19-C's schedule, not answerable from this snapshot alone).
- [ ] **Step 4: Write the note into the return report** (2-4 sentences + the counts). Do NOT create a repo file; do NOT commit. This task ships zero production code.

---

## Self-Review — spec coverage matrix

| Brief requirement | Task(s) | Discriminating test |
|---|---|---|
| §2(a) risk-unit floor form + value (RD-ruled) | 1, 2, 3 | T1 (VSTS caught), T2 (TVTX survives), T3 (normal unchanged), calibration guard |
| §2(a) exclude-vs-winsorize (RD-ruled) | 2 | default EXCLUDE; winsorize variant sketched |
| §2(b) epsilon-tolerant reader | 4, 5 | T4-math + T4 e2e (DINO recovered), passthrough, idempotence |
| §2(b) threshold + CALY posture (RD-ruled) | 1, 4, 5 | T5-math + T5 e2e (CALY held), calibration guard |
| §2(b) clamped-bar counter observability | 6 | T6 (manifest + summary) |
| §2(c) capture-timing trace (analysis) | 8 | n/a (no code) |
| §3 pure recompute / read-only / fresh artifact | all | `io.open_ro` untouched; no INSERT/UPDATE added; run_dir timestamped (unchanged) |
| §3 no `swing/` edit, no schema | all | file map is `research/harness/...` + `tests/...` only; testkit stays v27 |
| §3 log + archive verbatim (reader-side clamp) | 5 | clamp mutates in-memory `all_bars` only; collapse still on raw log OHLC |
| §3 0026 T4 criteria untouched | all | no `hypothesis_registry` / attribution / funnel-taxonomy change |
| §4 fixtures from REAL emitter data | 2, 4, 5, 7 | VSTS/TVTX/DINO/CALY geometry lifted verbatim from the live DB |

**Placeholder scan:** none — every code step carries complete code.
**Type consistency:** `simulate(..., adr_pct=None)`, `SimParams.risk_floor_*` (defaults 0.0), `clamp_ragged_bars(bars, *, max_pct) -> (list[Bar], list[ClampEvent])`, `_summary_lines(funnel, scorecard, clamp_summary)`, `clamped_bars: dict[(ticker, session), pct]`, `ohlc_clamp.clamped_bar_count` — consistent across Tasks 2-7.

## Post-merge measurement gate (brief §5.4 — NOT part of the code; the binding close)

After merge, a fresh full-corpus `run_harness` (turnkey) must show: VSTS heals from +27.333R to an excluded `degenerate_risk`; the A+ per-signal expectancy (was 13.667 on n=1) heals; the `invalid_ohlc` excluded count drops by the clamp-recovered signals (the ~38 attrition sheds all but the CALY-class residue); recovered signals enter the cohorts; the `ohlc_clamp.clamped_bar_count` appears in the manifest. **RD's pre-committed T4 confirmatory re-read** (the 2026-07-03 study §6) is the terminal measurement gate. No operator GUI witness (research lane); the operator authorizes the merge.
