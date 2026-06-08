# Minervini correct-entry exemplar recall — design spec

> **Status: design approved (brainstorm), pre-plan.** Produced by the post-Phase-15 copowers
> brainstorm cycle for the Minervini correct-entry exemplar-recall arc. Scoping source:
> [`docs/minervini-exemplar-recall-commissioning-brief.md`](../../minervini-exemplar-recall-commissioning-brief.md).
> Research-branch arc: all new code under `research/harness/minervini_exemplar_recall/` (+ one
> standalone `research/scripts/` one-off) and **exactly one** CLI registration in `swing/cli.py`.
>
> **This spec supersedes the brief's "REUSABLE AS-IS" infra map** where reality diverges: the
> Minervini OHLCV source is **Tiingo CSVs** (the operator built `tiingo_pull` because yfinance
> can't resolve the delisted names), not the yfinance Shape-A parquet the two reuse vehicles read;
> and the 5 detectors **hard-gate on a Stage-2 lookup against the production `candidates` table**,
> which has no rows for historical tickers. Both are handled below.

---

## 1. The question (recall / sensitivity, entry-side)

Given Minervini's documented **correct-entry** examples, **would our screening + filtering pipeline
have surfaced each one** (H1: `bucket_for` → `aplus`/`watch`), and **would any of the 5 V1 detectors
have fired** (H2: `geometric_score > 0`, fired-class matches the documented setup) — evaluated
strictly **point-in-time, no lookahead**, at/around the locked entry-crossing session? A **pass** =
our gates would have caught a known-good setup; a **miss localizes the silently-rejecting gate**.

This is a **true-positive recall** test, entry-side, complementary to (not a repeat of) the closed
2026-05-27 expectancy arc. It is **not** temporal-log-gated (uses Minervini ground truth, not
forward-walk accumulation).

---

## 2. Inputs (all present on disk)

- **Curated exemplar set:** `research/data/minervini-exemplars.csv` — **27 curated** rows
  (`curated=yes`). The 7 excluded rows are all `curated=no` (no usable point-in-time data source, or
  the iRobot stop-example) — so **`curated=yes` is the clean inclusion filter**; no notes-parsing.
  Of the 27, **8 are `unmapped`** (no detector analog → screening-recall only).
- **OHLCV archive (gitignored/local):** `research/data/tiingo/<symbol>.csv` (adjusted OHLCV), pulled
  by the existing `tiingo_pull.py`. Tiingo license is internal-use-only → never committed.
- **QA tooling (exists):** `tiingo_pull.py`, `qa_compare.py`, `qa_montage.py`.
- **Entry rule (operator-locked):** `entry_date` = **first close above the pivot** (base/handle high)
  on expanding volume — already pinned per exemplar; single-session anchors on it, window-sweep
  brackets it.

---

## 3. Architecture — Approach A (thin modules over leaf primitives)

The harness imports only **pure leaf functions** and owns everything around them. The two shipped
research harnesses (`aplus_v2_ohlcv_evaluator`, `pattern_cohort_evaluator`) are **not modified** —
their Codex-converged contracts stay frozen. Reused leaf imports:

- H1: `swing.evaluation.evaluator.evaluate_one`, `swing.evaluation.context.{CandidateContext,
  BatchContext, MarketContext}`, `swing.config.Config`.
- H2: `swing.pipeline.runner._pattern_detect_registry`, `swing.patterns.foundation.{generate_candidate_windows,
  current_stage}`.
- Schema for the synthetic stage DB: the production migration runner (`swing.data.db`).

**L2 LOCK held:** the harness import graph imports none of yfinance / schwabdev /
`swing.integrations.schwab` / `swing.data.ohlcv_archive`. (The VICR materializer in §4.2 imports
yfinance but lives **outside** the harness package and is never imported by it.) A test greps the
harness module set to enforce this.

**Corollary simplification — no production DB needed.** H1 is pure on `CandidateContext`; equity uses
the $7500 floor surrogate; stage is synthetic. So the harness opens **no** `swing.db` (unlike the two
reuse vehicles, which require `--db`).

### 3.1 Module layout (`research/harness/minervini_exemplar_recall/`)

| Module | Responsibility |
|---|---|
| `exemplar_reader.py` | Parse the CSV → `ExemplarRow`; filter `curated=yes`; parse `entry_date` (`YYYY`/`YYYY-MM`/`YYYY-MM-DD`) → concrete date + `date_precision`; carry `detector_class` (incl. `unmapped`); resolve `SYMBOL_OVERRIDE`. |
| `ohlcv_reader.py` | Tiingo CSV → canonical capitalized **adjusted** OHLCV on a `DatetimeIndex`; `<=asof_date` inclusive slice (same contract as the V2 reader); `min_bars` parameter (not hard-200); typed coverage error. |
| `rs_proxy.py` | Build `BatchContext`: **P0** `fallback_spy`; **P1** TT8-NA degenerate; per-exemplar path flag. |
| `screen_eval.py` | H1 core: assemble `CandidateContext`, `evaluate_one`, extract bucket + 18 criteria, classify H1 outcome + load-bearing gate. |
| `stage_db.py` | Throwaway SQLite (schema via the production migration runner) seeding `current_stage`: production-faithful + stage-isolated variants. |
| `detector_eval.py` | H2 core: bars → `generate_candidate_windows` → 5 detectors geometric-only against the synthetic stage conn → fired? + class-match; both stage variants; skip taxonomy. |
| `timing.py` | Single-session + window-sweep `[entry−60bd, entry+5bd]` best-of orchestration. |
| `control_cohort.py` | Same-ticker random non-entry-date sampling (≥120bd from entry, deterministic). |
| `scorecard.py` | Recall metrics + per-gate attribution + stratified denominators + bootstrap CI + control base rate. |
| `output.py` | `results.csv` / `per_session.csv` / `summary.md` / `manifest.json`. |
| `run.py` | argparse entry; delegated to by the single `swing/cli.py` registration. |

**Out-of-harness one-off:** `research/scripts/materialize_vicr_yfinance.py` — imports yfinance, pulls
VICR ≥1990, writes `research/data/tiingo/VICR.csv` in **Tiingo column format** (overwriting the
shallow 1991-11 pull), with a provenance header. Not imported by the harness.

---

## 4. Data layer

### 4.1 Tiingo reader (`ohlcv_reader.py`)
- Reads `research/data/tiingo/<symbol>.csv`; maps `adjOpen/adjHigh/adjLow/adjClose/adjVolume` →
  `Open/High/Low/Close/Volume` (split/dividend-adjusted, matches yfinance `auto_adjust`); parses
  `date` → `DatetimeIndex` (tz-naive, ascending).
- `SYMBOL_OVERRIDE = {"EMEX": "ELX", "HOOK": "BREW"}` (mirrors `tiingo_pull`).
- `read_sliced(symbol, asof_date, *, min_bars)` → bars with `index.date <= asof_date` (inclusive,
  backward-looking anchor per the cumulative gotcha); raises a typed coverage error when
  `len(sliced) < min_bars`. H1 calls with `min_bars=1` (so insufficient-history is *detected*, not
  raised); H2 calls with a small detector floor.

### 4.2 SPY benchmark + VICR
- Extend `tiingo_pull.py` to always include **SPY** in the unique-symbol set (one deep pull) for the
  `fallback_spy` RS proxy. SPY (SPDR) inception is 1993-01 → pre-1993 exemplars fall to P1.
- `research/scripts/materialize_vicr_yfinance.py` produces `VICR.csv` (≥1990) so VICR's Feb-1991
  entry is evaluable; the reader consumes it identically (provenance recorded in `manifest.json`).

### 4.3 Exemplar reader (`exemplar_reader.py`)
- `ExemplarRow(exemplar_id, ticker, tiingo_symbol, setup_label, detector_class, entry_anchor: date,
  date_precision, buy_point_price | None, source, page, notes)`.
- `entry_anchor` parses `YYYY`/`YYYY-MM`/`YYYY-MM-DD` (mid-period default for coarse precision, per
  `tiingo_pull.entry_anchor`); `date_precision` retained so the scorecard can flag low-precision
  single-session results.

---

## 5. H1 — screen → bucket (`screen_eval.py`)

For one `(exemplar, session)`:
1. Tiingo bars sliced `<= session` (`min_bars=1`).
2. `BatchContext` from `rs_proxy`; `current_equity = 7500.0` (flagged surrogate); `MarketContext()`.
3. `candidate = evaluate_one(ctx)` → `bucket` + 18 `CriterionResult` (8 `trend_template` + 9 `vcp`
   + 1 `risk`).
4. **H1 outcome taxonomy:**
   - `no_data` — no Tiingo bars cover the session.
   - `skip_insufficient_history` — `len(sliced) < SCREENABLE_FLOOR`, where
     `SCREENABLE_FLOOR = 200 + cfg.trend_template.rising_ma_period_days` (=221; the true floor for a
     full TT pass — TT3 needs 200 + `rising_period` bars of `sma200`). TT is all/mostly NA → bucket
     forced to `skip` by NA, **not** by a gate. **Excluded from gate attribution.**
   - `surfaced_aplus` / `surfaced_watch` — `bucket in {aplus, watch}`.
   - `skip_gate_rejection` — `bucket == skip` AND screenable → a real gate rejected a known-good
     setup. Attribute the load-bearing gate.
5. **Load-bearing-gate attribution** (skip_gate_rejection only), replaying `bucket_for`'s order:
   - `risk` non-pass → `first_rejecting_gate = risk_feasibility`.
   - else TT: failing TT gates outside `allowed_miss_names` are load-bearing; if all fails are
     allowed but `tt_passes < min_passes`, the localizer is the `min_passes` shortfall (the failed
     TT gates are still named).
   - else VCP: `vcp_fails > 2` → `first_rejecting_gate = vcp` (the failed VCP criteria named).
   - Emits one `first_rejecting_gate` (aggregated by the scorecard) + the full `failing_gates` list.

### 5.1 RS proxy (`rs_proxy.py`)
- **P0 `fallback_spy`** (default): `returns_12w_by_ticker = {ticker: r}` where `r` = the exemplar's
  trailing `horizon_weeks*5`-bar return from its own sliced bars; `spy_return_12w` = SPY's same-window
  return as-of the session; `universe_tickers = ()` (empty → ticker outside universe →
  `compute_rs` returns `fallback_spy`: TT8 passes if `excess >= +fallback_extreme_pct%`, fails if
  `<= -fallback_extreme_pct%`, else NA). Verified against `swing.evaluation.rs.compute_rs`.
- **P1 TT8-NA** (degenerate fallback): when SPY bars don't cover the session (pre-1993) or the
  exemplar lacks `horizon_weeks*5+1` bars → empty `returns_12w_by_ticker` → `compute_rs` returns
  `unavailable` → TT8 NA, absorbed by `allowed_miss_names=["TT8_rs_rank"]`. Per-exemplar flag records
  P0-vs-P1.
- Note the asymmetry vs §6: P0 TT8 *passing* gives 1 slack toward `min_passes=7` (TT can reach 8/8);
  P1 has zero slack (needs all of TT1–TT7).

---

## 6. H2 — detector fired (`detector_eval.py` + `stage_db.py`)

All 5 detectors hard-gate on `current_stage(conn, ticker, asof) == "stage_2"`, and
`_TREND_TEMPLATE_REQUIRED_PASS_COUNT = 8` (Stage-2 requires a `candidates` row whose
`candidate_criteria` has **8** `trend_template` passes — *stricter* than the aplus bucket, which
treats TT8 as an allowed miss). Historical tickers have no production rows, so stage must be seeded.

### 6.1 Synthetic stage DB (`stage_db.py`)
- Build a throwaway SQLite whose schema comes from the **production migration runner** (zero DDL
  drift; never hand-authored). Writable (it is a research scratch DB, not production).
- Per evaluated session, insert one synthetic candidate keyed at `action_session_date = session`,
  under two variants:
  - **production-faithful** — `candidate_criteria` `trend_template` rows = that session's H1 TT
    results → `current_stage` returns `stage_2` iff H1 confirms 8/8 TT.
  - **stage-isolated** — 8 forced `pass` rows → `current_stage` always returns `stage_2`.
- `current_stage` selects the most-recent candidate with `action_session_date <= asof`; per-session
  rows make the faithful stage reflect that session's TT exactly. (Insert all swept sessions, then
  query each — at session S the most-recent `<= S` is S itself.)

### 6.2 Detector loop
For one `(exemplar, session, stage-variant)`:
1. Tiingo bars sliced `<= session` with a small detector floor (not 200).
2. `generate_candidate_windows(sliced, "zigzag_pivot", ticker=…, timeframe="daily")`.
3. For each `(window, detector)`: `geometric_score = detector_fn(sliced, window, conn=stage_conn,
   ticker=…, asof_date=session).geometric_score`; **`fired = geometric_score > 0`** (geometric-only,
   no template-match Pass 2).
4. Per-window/detector failures caught into a skip taxonomy mirroring the cohort harness (never
   silent, per gotcha #27): coverage / window-generation / no-windows / detector-error.
5. Per `(exemplar, session)` verdict, under **both** stage variants:
   `fired_expected_class` (the documented `detector_class` fired), `fired_any_class`, `fired_classes`.
   `unmapped` exemplars have no expected class → excluded from the per-detector recall denominator;
   their any-fire is reported separately as detector noise.

---

## 7. Timing modes (`timing.py`)

Both modes run per exemplar and report side by side:
- **single-session** — evaluate at `entry_anchor`. Coarse-precision (month/year) exemplars are
  anchored on the parsed date but flagged low-precision (window-sweep is the reliable mode for them).
- **window-sweep** — sessions in **`[entry−window_back, entry+window_fwd]`** (defaults 60/5) as
  **positional** offsets in the full Tiingo bar history: `entry_pos` = first bar with
  `date >= entry_anchor`; window = `bars[max(0, entry_pos-window_back) : entry_pos+window_fwd+1]`.
  The start index is clamped to 0 (a negative start would Python-wrap to the tail — exactly the
  failure mode for young names where `entry_pos < window_back`). The end index naturally truncates at
  the last available bar. Each session is an `asof_date` evaluated `<=`-sliced → **no-lookahead holds
  per session**. If `entry_anchor` falls beyond the last bar (coverage gap), the exemplar yields
  `no_data` for that mode.
- **Aggregation:** H1 best bucket by `aplus(2) > watch(1) > skip(0)` (+ best H1 outcome); H2
  `fired_expected_class` if it fired at **any** session (per stage variant), with firing session(s)
  recorded; per-session detail retained for `per_session.csv`.

---

## 8. Negative-control cohort (`control_cohort.py`)

- For each exemplar ticker, sample **K (default 5)** random sessions from its Tiingo history with:
  `|session_pos − entry_pos| >= 120` bars, outside the sweep window, and `>= SCREENABLE_FLOOR`
  preceding bars (so H1 can run a fair comparison).
- Deterministic: a fixed base seed combined with the exemplar index (reproducible; documented in the
  manifest). Standard-library `random` (this is harness code, not a Workflow script).
- Each control runs the identical H1 + H2(both stage variants) using its parent exemplar's expected
  `detector_class`. Yields the **false-fire base rate** — "does this same stock's detector fire on
  random days vs at the documented pivot?"
- `unmapped` exemplars contribute screening (H1) controls only.

---

## 9. Recall scorecard (`scorecard.py`)

Computed for **both timing modes**; H2 for **both stage variants**:
- **Bucket distribution** — exemplar counts by best H1 outcome (`surfaced_aplus` / `surfaced_watch` /
  `skip_gate_rejection` / `skip_insufficient_history` / `no_data`).
- **Screening recall, stratified** — full-set `(aplus+watch)/N_total` **and** screenable-subset
  `/N_screenable` (excludes insufficient-history + no-data); aplus-only and watch-inclusive variants.
- **Per-gate first-rejection attribution** — histogram of `first_rejecting_gate` over
  `skip_gate_rejection` exemplars (the localizer) + per-gate pass rate over the screenable subset.
- **Per-detector recall (H2)** — `N(fired expected class)/N(mapped exemplars of class)` per class +
  overall, under **both stage variants**; the **isolated − faithful delta** attributes a detector
  miss to the Stage-2 gate vs the geometric criteria. Plus class-match (`fired_expected` vs
  `fired_any`).
- **Negative control** — same stat shape on the control cohort (false-fire base rate).
- **Bootstrap 95% CI** — resample exemplars with replacement (B default 2000) on the key fractions;
  **primary CI on the screenable subset**; full-set reported alongside with attrition called out.

---

## 10. Outputs + CLI

### 10.1 `output.py` → `exports/research/minervini-exemplar-recall-<ISO>/`
- `results.csv` — per `(exemplar × timing_mode)`: H1 outcome, best bucket, `first_rejecting_gate`,
  H2 `fired_expected_class` (faithful + isolated), `fired_classes`, data-source + RS-path flags, bar
  count, screenable flag.
- `per_session.csv` — window-sweep drill-down per `(exemplar, session)`: bucket, H1 outcome,
  per-class fire (both stage variants).
- `summary.md` — the scorecard (all of §9) + a limitations footer.
- `manifest.json` — harness version, exemplar-set hash, `n_total / n_screenable / n_excluded`,
  per-exemplar data-source provenance (Tiingo / VICR-yfinance) + RS-path, config snapshot
  (`min_passes`, `allowed_miss_names`, `rs_rank_min_pass`, `fallback_extreme_pct`, `horizon_weeks`,
  `rising_ma_period_days`), window/control params + seed, bootstrap B, started/finished UTC, coverage
  + skip-reason counters.
- **ASCII-only** in every printed/written string (Windows cp1252 gotcha); no `$`/`^`/`_`/`\` in any
  matplotlib title path (plots, if any, are in the existing `qa_compare`).

### 10.2 CLI
- `python -m research.harness.minervini_exemplar_recall.run --exemplars-csv PATH --tiingo-dir PATH
  --output-dir DIR [--window-back 60] [--window-fwd 5] [--control-k 5] [--bootstrap-b 2000]
  [--only id1,id2]`.
- **One** `swing/cli.py` registration: `swing diagnose minervini-recall` (mirrors
  `aplus-sensitivity-v2`), delegating to `run.run_harness`. `ValueError → click.ClickException` at
  the boundary.
- **No `--db`** (H1 pure; equity floor; stage synthetic).

---

## 11. Testing strategy (TDD per task)

Discriminating tests:
- **reader** — `adj*`→capitalized mapping; `<=asof` inclusivity; `SYMBOL_OVERRIDE`; `min_bars` raise.
- **rs_proxy** — P0 excess computed correctly (pass/fail/NA boundaries at `±fallback_extreme_pct`);
  P1 when SPY missing / short history; per-exemplar path flag.
- **screen_eval** — one discriminating test per H1 outcome: `surfaced`, `skip_gate_rejection` with the
  **correct localizer**, `skip_insufficient_history` at `<221` bars, `no_data`. Per the
  regression-arithmetic discipline, each asserts the value differs under the pre/post path so the test
  genuinely distinguishes.
- **stage_db** — faithful returns `stage_2` iff 8/8 TT pass; isolated always `stage_2`; schema builds
  via the migration runner.
- **detector_eval** — a planted Stage-2 window fires (`geometric>0`); under faithful with `<8` TT it
  is gated off (`0`); `unmapped` excluded from the denominator; skip taxonomy populated, never silent.
- **timing** — positional window offsets; best-of ordering; no-lookahead per session.
- **control_cohort** — `>=120bd` gap; outside sweep window; deterministic seed; `>=SCREENABLE_FLOOR`
  preceding bars.
- **scorecard** — stratified denominators; attribution histogram; bootstrap CI shape; control rate.
- **CLI** — `ValueError→ClickException`; **ASCII stdout via a subprocess-through-PowerShell test**.
- **L2-LOCK grep test** — no forbidden imports anywhere in the harness module set.

Fixtures: small real-Tiingo slices for a couple of exemplars + synthetic for edge cases; **derive
fixtures from real reader output** (synthetic-fixture-vs-production shape-drift gotcha).

---

## 12. Limitations (for the study writeup)

1. **OHLCV archive temporal mutation (#24/#26)** — Tiingo bars are adjusted and may drift on re-pull;
   an immutable snapshot is the ideal. Characterize as an L6-style limitation.
2. **Split adjustment** — `buy_point_price` labels are nominal; the harness anchors on **date**, not
   price (optional price sanity-check only).
3. **SPY inception 1993** — pre-1993 exemplars (VICR 1991) use P1 TT8-NA; flagged per exemplar.
4. **RS proxy is SPY-relative**, not a true universe rank; proxy-universe RS is a future rigor upgrade.
5. **Faithful Stage-2 requires 8/8 TT** (stricter than the aplus bucket, which allows TT8 miss) — a
   real production quirk; surfaced as a finding via the faithful-vs-isolated delta, not hidden.
6. **Insufficient-history is irreducible** — the five young post-IPO names (QSII, JNPR, AMZN-1997,
   MELI, BODY) lack ~221 bars at entry because the stock wasn't public earlier; no data source or
   threshold tuning closes this. A young-name screening variant is a candidate **future** arc.
7. **`current_stage` models stage_2-vs-not only** (V1 thin wrapper; stages 1/3/4 are V2-deferred).
8. **Small n** (~20–27 after attrition) → descriptive + bootstrap CI; **no inferential claim**.

---

## 13. Deliverables (brief §11)

- **Method-record stub** → `research/method-records/minervini-exemplar-recall.md` (per `_template.md`).
- **Study design** → `research/studies/2026-06-08-minervini-exemplar-recall.md` (per the
  `earnings-proximity-exclusion.md` / `2026-05-24-pattern-cohort-detection.md` precedent).
- **Harness** → the `research/harness/minervini_exemplar_recall/` modules in §3.1 + one CLI
  registration + the `research/scripts/materialize_vicr_yfinance.py` one-off.
- **Curated exemplar CSV** — already present.
- **Outputs** → `exports/research/minervini-exemplar-recall-<ISO>/`.

**Source-of-truth correction protocol (V2.1 §VII.F):** any deployable finding (a gate re-tune, a
young-name screen) routes through it — never a direct patch.

---

## 14. Resolved open questions (brief §10 + arc-specific)

| # | Question | Resolution |
|---|---|---|
| §10.1 | Baseline / null | Descriptive + per-gate attribution **+ negative-control cohort** (false-fire base rate); no inferential test. |
| §10.2 | RS reconstruction | **P0 SPY-relative `fallback_spy`** primary; P1 TT8-NA degenerate fallback (pre-1993); proxy-universe deferred. |
| §10.3 | Template-match Pass 2 | **Off — geometric-only** (`fired = geometric_score > 0`). |
| §10.4 | Window-sweep aggregation | `[entry−60bd, entry+5bd]` positional; best bucket `aplus>watch>skip`; detector fired if fired at any session. |
| §10.5 | Load into `pattern_exemplars` | **No** — CSV stays CSV (avoids self-match circularity + schema/phase work). |
| §10.6 | Sizing / framing | Descriptive + **bootstrap 95% CI**; primary CI on the screenable subset. |
| arc | Negative-control sampling | **Same tickers, random non-entry dates** (≥120bd from entry; reuses Tiingo). |
| arc | VICR data source | **One-off out-of-harness yfinance materialization** → `VICR.csv` (Tiingo format); L2 LOCK intact. |
| arc | Young-name (`<221` bar) handling | Distinct `skip_insufficient_history` class + **stratified recall** (full + screenable); excluded from gate attribution; H2 still runs at the detector's true min-bars. |
| arc | Detector Stage-2 gate | Seed a synthetic stage DB in **both** variants (production-faithful from H1 + stage-isolated forced); the delta attributes H2 misses to the gate vs the geometry. |
