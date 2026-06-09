# Minervini primary-base (young-name) screen recall — design spec

> **Status: design approved (brainstorm), pre-plan.** Post-Minervini-recall follow-up #1 (the
> young-name screening variant). Scoping source:
> [`docs/young-name-screening-variant-commissioning-brief.md`](../../young-name-screening-variant-commissioning-brief.md).
> Research-branch arc: new code under `research/harness/minervini_primary_base_recall/`; exactly
> **one** CLI registration in `swing/cli.py`. Research study only — any deployable young-name screen
> routes through the source-of-truth correction protocol (V2.1 §VII.F), NOT a direct patch.

## 1. The question

The Minervini correct-entry recall study
([`research/studies/2026-06-08-minervini-exemplar-recall.md`](../../../research/studies/2026-06-08-minervini-exemplar-recall.md))
found **7/27 exemplars structurally un-screenable** (`skip_insufficient_history`, < ~221 bars,
newly-public): the Trend Template needs SMA200 + a rising-200MA window a young stock cannot have, yet
Minervini explicitly buys young post-IPO leaders. His documented methodology for them is the
**primary base** (TWoSMW Ch.11). **Question:** does a point-in-time **primary-base screen**, grounded
in Ch.11, **surface (recall)** Minervini's documented primary-base entries while staying **selective
(precision)** against random young-stock windows of the same names? A pass = a young-name screen that
catches the documented primary-base emergences without firing indiscriminately.

This is **recall+precision-motivated** (the recall study localized the exact gap), **H1-screening
only** (the primary base is a screening concept; H2 detectors stay out), and a **research study**
(reuses the recall harness; deployment is a separate §VII.F step).

## 2. Minervini's primary base (TWoSMW Ch.11, quantified)

- **Minimum trading history** — "at least a couple of months of trading activity" to prove mettle.
- **Base duration** — "a base of at least three to five weeks" (a corrective period ≥3 weeks);
  longer (~1yr) bases also valid.
- **Correction depth, graduated by duration** — 3-week consolidations "should not correct more than
  25 percent"; longer ones up to 35%, and ~1yr bases up to 50%, and still be sound.
- **Emergence** — "successful emergence to new high ground from its first viable consolidation"
  (all-time high, or a constructive consolidation near it).
- **Primary = the FIRST buyable base after the IPO.**

Documented Ch.11 examples (figure captions): AMZN-1997 (Fig 11.1), YHOO (Fig 11.3), JNPR (Fig 11.7),
DKS (Fig 11.6), BODY (~`md:4111`), iRobot (Fig 11.8, excluded — a stop example). The CSV MELI row is
**excluded** — it is a VCP/failure-reset (Fig 10.33), not a primary base (the book's MELI primary base
is a different Oct-2010 entry not in the CSV).

## 3. Cohort (honest n ≈ 3 evaluable sub-floor — a proof-of-concept, NOT a powered study)

Only names Minervini **frames in Ch.11 as a primary base** belong (a young *VCP* is a category
mismatch). Codex R1 tightened this materially — see the **headline n-shrinkage** below. Curated
`exemplar_id`s (resolved from `research/data/minervini-exemplars.csv` via the recall harness's
`exemplar_reader`; bar counts are exact-through-parsed-anchor, emitted to the manifest):

| exemplar_id | ticker | role | bars | precision |
|---|---|---|---|---|
| `twosmw-fig11-1-amzn` | AMZN-1997 | sub-floor primary base (Ch.11 Fig 11.1) | 75 | **month → sweep-only** |
| `ttlc-fig10-1-body` | BODY | sub-floor primary base (Ch.11 ~`md:4111`, explicit) | 57 | day |
| `twosmw-fig11-6-dks` | DKS | sub-floor primary base (Ch.11 Fig 11.6, explicit) | 115 | **month → sweep-only** |
| `twosmw-fig11-7-jnpr` | JNPR | sub-floor, but **25 bars < MIN_HISTORY_BARS=40** → `history`-excluded | 25 | day |
| `twosmw-fig11-3-yhoo` | YHOO | sufficient-history **positive control** | 302 | day |

**Two Codex-R1 corrections shrank the cohort from the "~6" I floated:**
- **MELI REMOVED (R1.M4).** The CSV `twosmw-fig10-33-meli` (entry 2007-12-10) is a **VCP** (Fig 10.33),
  not a primary base; the book's MELI *primary base* is a *different* Oct-2010 entry not in the CSV. I
  mis-attributed it. MELI is a young-VCP (same out-of-scope category as QSII).
- **JNPR is `history`-excluded (R1.M2), reported not counted as a screen miss.** At 25 bars (~5 weeks)
  it is **below Minervini's own ≥-2-month minimum** ("at least a couple of months of trading
  activity") — the screen *correctly* cannot evaluate it. This is itself a finding (a documented entry
  below the book's own stated floor), surfaced via a stratified denominator, NOT a gate failure.

So the **evaluable sub-floor documented-primary-base cohort = {AMZN-1997, BODY, DKS} = 3** (of which
only BODY is day-precision → single-session-eligible; AMZN-1997 + DKS are month-precision →
sweep-only, R1.M3), plus **YHOO** as a sufficient-history positive control, plus **JNPR** reported as
below-minimum. **n_evaluable ≈ 3.** This is a **mechanism-validation proof-of-concept**, not a powered
study; raw fractions are reported first, Wilson as a mechanical interval only. **Corpus expansion
(Google/Starbucks/Reebok/MSFT/Intel/Rambus/RIMM Ch.11 primary bases) is now strongly advised** — it
was declined for V1, but the n≈3 reality makes it the obvious immediate sequel. (Operator: this n is
smaller than the "~6" the ship-at-existing decision assumed; flagged for re-confirmation at spec review.)

## 4. Architecture — Approach A (new sibling harness over frozen leaves)

`research/harness/minervini_primary_base_recall/`. The shipped `minervini_exemplar_recall` harness
stays **frozen**; this arc imports its reusable leaves. **L2 LOCK** held: imports none of yfinance /
schwabdev / `swing.integrations.schwab` / `swing.data.ohlcv_archive`. The only `swing/` change is the
one CLI registration. **No production DB** (the screen is pure on bars; no equity, no stage).

| Module | Responsibility |
|---|---|
| `primary_base_screen.py` | `PrimaryBaseVerdict` + `screen_at(bars, asof_date)` — the Ch.11 criteria over `extract_zigzag_swings`. |
| `cohort.py` | The curated documented-primary-base `exemplar_id` list (§3) + per-id book citation; resolves rows via `exemplar_reader`. |
| `timing.py` | Single-session (day/exact only) + window-sweep best-of over `screen_at`: day/exact precision uses `[entry−60bd, entry+5bd]`; **month precision uses the full documented month + slack** (`[first_trading_day_of_month−60bd, last_trading_day_of_month+5bd]`). |
| `precision_control.py` | **Own** young-window control sampler (pre-filters candidate positions to `[MIN_HISTORY_BARS−1, MAX_CONTROL_AGE_BARS−1]` BEFORE sampling — *not* the frozen full-archive `sample_control_anchors`, R2.M1); runs the screen at control anchors. |
| `scorecard.py` | Recall + precision + Wilson + ticker-clustered bootstrap, both timing modes. |
| `output.py` / `run.py` | `results.csv` / `per_session.csv` / `summary.md` / `manifest.json` + one CLI reg. |

**Reuse (frozen leaves), verified seams:**
- `minervini_exemplar_recall.ohlcv_reader` — `read_full(symbol, *, tiingo_dir)`, `slice_to(bars, asof_date)`, `read_sliced(symbol, asof_date, *, tiingo_dir, min_bars)`.
- `minervini_exemplar_recall.exemplar_reader` — `read_exemplars(csv_path) -> list[ExemplarRow]` (`exemplar_id, ticker, tiingo_symbol, entry_anchor, date_precision, …`).
- `minervini_exemplar_recall.control_cohort` — **`ControlAnchor` only.** The frozen `sample_control_anchors`
  draws uniformly from the *full post-floor archive*, so a post-hoc young-age filter would erase nearly
  all controls for deep-history names (R2.M1: ~0 young controls for AMZN/DKS/YHOO). Instead
  `precision_control.py` writes its **own** young-window sampler that **pre-filters candidate positions
  to `[MIN_HISTORY_BARS-1, MAX_CONTROL_AGE_BARS-1]` BEFORE sampling** (then the same `>=CONTROL_GAP_BARS`-
  from-entry + outside-sweep-window + deterministic-seed rules), so it actually returns young controls.
- `minervini_exemplar_recall.scorecard` — `wilson_interval(successes, n, z=1.96)`, `ticker_clustered_bootstrap(rows, value_fn, *, b, base_seed)`.
- `swing.patterns.foundation` — `extract_zigzag_swings(bars, initial_threshold_pct, monotonic_narrow=False) -> list[Swing]` (the exact `Swing` field access pinned at writing-plans).

## 5. The primary-base screen (`primary_base_screen.py`)

`screen_at(bars, asof_date) -> PrimaryBaseVerdict` — bars sliced `<= asof_date` (point-in-time; the
first available bar is the IPO proxy). **"Fired" = a buyable primary-base emergence**, all criteria
holding:

1. **History gate** — `len(bars) >= MIN_HISTORY_BARS` (=40, ~2 months, "a couple of months of
   trading activity"). Below → `history` (not-yet-evaluable; e.g. JNPR at 25 bars, §3).
2. **Base identification (explicit algorithm, R1.M5)** — `extract_zigzag_swings(bars, ZIGZAG_THRESHOLD_PCT=3.0)`
   returns *closed* `Swing` legs (`start_date`/`end_date`/prices/direction/`depth_pct`/calendar
   `duration_days`, Close-only; no developing final leg). The base:
   (a) `base_high` = the highest swing-high pivot in `[IPO, asof]` whose subsequent leg is a
   down-swing (the pre-base peak); `base_start` = that pivot's bar.
   (b) `base_low` = the lowest Close in `[base_start, asof]` (covers single- OR multi-contraction
   bases — not just one closed down-swing).
   (c) **Calendar→bar mapping (R1.m3):** map every `Swing` `start_date`/`end_date` back to integer
   bar *positions* in the sliced frame; ALL of duration (crit 3) and depth (crit 4) are computed in
   **bars**, never `Swing.duration_days` (calendar).
   (d) **Fallbacks:** no qualifying down-swing → `no_base`; an IPO-day high with no prior pivot →
   `no_base`; "constructive consolidation near ATH" with a shallow (<threshold) pullback that zigzag
   misses → `no_base` for V1 (documented limitation; a tighter zigzag threshold is a sweepable knob).
3. **Base duration** — `(asof_pos - base_start_pos) >= MIN_BASE_BARS` (=15 bars, "at least three to
   five weeks"), in bars.
4. **Correction depth ≤ graduated cap (R1.M7, trading-week-faithful)** — `(base_high - base_low)/base_high`
   ≤ `DEPTH_CAP_BY_DURATION` keyed on base duration in **bars**: `<=25 bars (~5wk): 0.25` (Minervini:
   "shorter three-week consolidations should not exceed 25%"); `26-200 bars: 0.35` ("not correct more
   than 25 to 35 percent"); `>200 bars (~1yr): 0.50` ("year-long bases can correct up to 50%"). A
   deliberately literal mapping of the Ch.11 prose; the boundaries are a sweepable knob.
5. **Emergence to new high ground — the FIRST crossing event, not a one-bar recross (R1.M6)** — the
   close crosses above `base_high` at `asof` AND has not done so earlier in the base:
   `close[asof-1] <= base_high < close[asof]` **AND `max(close[base_start_pos : asof_pos]) <= base_high`**.
   The second clause makes it the *first* emergence — without it the bare one-bar recross would
   falsely fire on a later recross after a failed breakout/reset (exactly the failure-reset trap).
   This is "currently above base_high" rejected as a *state* (would fire across the whole uptrend).
   No-lookahead holds (only bars `<= asof`). The window-sweep gives temporal slack for coarse-precision
   entries; single-session must land on the actual cross bar.
6. **Primary = first base — the FIRST-FIRE test (R2.M3, mechanical)** — `asof` is the FIRST session in
   the name's post-IPO history at which criteria 1–5 ALL hold. Operationally: replay criteria 1–5 over
   every prior as-of session `s` in `[MIN_HISTORY_BARS−1, asof_pos−1]`; if ANY earlier `s` fired the
   full screen, reject `asof` as `not_primary` (this is a later base). Cost is `O(N²)` per name but
   bounded by young-name history length (≤~300 bars), so cheap. This makes "primary = first base"
   computable point-in-time with no lookahead (every replay reads only bars `<= s`).

`PrimaryBaseVerdict`: `fired: bool` + diagnostics (`base_start_date`, `base_high`,
`correction_depth_pct`, `base_duration_bars`, `emergence_close`) + **`first_rejecting_criterion`** when
not fired (one of `history` / `no_base` / `duration` / `depth` / `no_emergence` / `not_primary`) — the
localizer. All thresholds are documented module constants citing Ch.11.

**Structural note (vs the recall arc):** this is an **emergence/breakout** screen — it fires *at* the
breakout, not during the coil (unlike VCP). So for **day/exact-precision** entries single-session-at-entry
*should* fire (the documented entry *is* the emergence). **Whether single-session ≈ window-sweep is a
HYPOTHESIS to test, not a structural guarantee (R1.M10)** — month-precision anchors (AMZN-1997, DKS;
sweep-only per §6) and any buy-point-vs-close ambiguity can still open a gap, as the recall study's
0.25-vs-0.90 timing split warns. Report the gap; don't assume it.

## 6. Recall + precision measurement

- **Recall (cohort).** **window-sweep** `screen_at` best-of, firing session(s) recorded — the reliable
  mode for ALL exemplars. Window:
  - **day/exact precision:** `[entry−60bd, entry+5bd]` (positional, start clamped to 0).
  - **month precision (AMZN-1997, DKS):** the parsed anchor is an arbitrary first-of-month, so the
    sweep spans the **whole documented calendar month + slack** — `[first_trading_day_of_month − 60bd,
    last_trading_day_of_month + 5bd]` — so the emergence can occur anywhere in the documented month
    (R2.M2). **single-session** `screen_at(≤entry_anchor, entry_anchor)` is reported **only for
    day/exact precision**; month rows are **sweep-only** (their parsed first-of-month anchor isn't the cross bar).
  - **Single-session sub-floor recall is BODY-only → n=1, reported as a single yes/no, NO interval**
    (R2.m1: AMZN-1997/DKS are month-precision sweep-only; JNPR is history-excluded). Window-sweep
    sub-floor recall is over {AMZN-1997, BODY, DKS} (n=3).
  - **Stratified denominators:** evaluable sub-floor {AMZN-1997, BODY, DKS} · JNPR `history`-excluded
    note · YHOO positive control. Per-miss `first_rejecting_criterion`.
- **Precision (same-ticker temporal specificity).** `precision_control.py`'s **own young-window
  sampler** (R2.M1): candidate positions **pre-filtered to `[MIN_HISTORY_BARS−1, MAX_CONTROL_AGE_BARS−1]`
  (=`[39, 503]`, ~first 2 years post-IPO) BEFORE sampling**, then `>=CONTROL_GAP_BARS` from entry +
  outside the sweep window + a deterministic per-exemplar seed; `k` (=5) young controls if available.
  (Pre-filtering, not post-filtering, is what actually yields young controls for deep-history names.)
  **Primary precision estimand = single-session per-anchor fire rate** (the right comparison for an
  *event* screen); the window best-of rate is reported **separately and labeled** (R1.M9), never
  conflated (a 66-session window mechanically inflates vs a one-session event probability). A name
  with no eligible young controls → precision NA (not 0).

## 7. Scorecard (`scorecard.py`)

Reuse recall-harness primitives:
- **Recall — raw fractions FIRST** (R1.m4): report `N(fired)/N` as explicit counts (e.g. "2/3
  sub-floor sweep-mode") with the exemplar_ids, BEFORE any interval. Window-sweep over the evaluable
  sub-floor cohort; single-session only over the day-precision subset; YHOO positive control + the
  JNPR `history`-exclusion reported separately.
- **Wilson 95%** labeled a **mechanical interval at n≈3, NOT evidence of stable performance**;
  ticker-clustered bootstrap exploratory-only. (At n≈3 these are illustrative.)
- **Per-criterion first-rejection histogram** across misses (the localizer).
- **Precision** — the **single-session per-anchor fire rate** is the primary estimand (event screen);
  the window best-of rate is reported separately and labeled, never conflated (R1.M9). Exemplar
  emergence fire vs young-window same-ticker control fire.
- Descriptive proof-of-concept; **n≈3 → no inferential claim; the headline output is "do the
  mechanics fire on the documented primary bases" + "is corpus expansion warranted" (yes).**

## 8. Outputs + CLI

- `exports/research/primary-base-recall-<ISO>/`: `results.csv` (per exemplar×mode: fired,
  `first_rejecting_criterion`, base diagnostics, data source), `per_session.csv` (sweep drill-down),
  `summary.md` (recall + precision + Wilson + criterion histogram + YHOO control), `manifest.json`
  (cohort, **exact per-exemplar bar-count-through-anchor + date_precision** (R1.m2), thresholds with
  Ch.11 citations, control params + seed + `MAX_CONTROL_AGE_BARS`, n_evaluable, per-exemplar
  provenance, **per-exemplar `eligible_control_count_before_sampling`** (R3.m1 — so empty/thin-control
  cases are transparent; verified non-empty for the current rows: AMZN 309, BODY 328, DKS 270,
  YHOO 226), `l2_lock_preserved`, UTC timestamps). **ASCII-only.** `.gitignore` allowlist mirrors the
  minervini-recall outputs (track `summary.md`/`manifest.json`/`results.csv`/`per_session.csv`).
- **CLI:** `swing diagnose primary-base-recall` (mirror `minervini-recall`; **no `--db`**; flags
  `--exemplars-csv --tiingo-dir --output-dir --window-back 60 --window-fwd 5 --control-k 5
  --bootstrap-b 2000 --only`); `ValueError → click.ClickException`.

## 9. Testing (TDD per task)

- **primary_base_screen** — one discriminating test per criterion, each with `WRONG-PATH`/`RIGHT-PATH`
  values: a planted primary base whose close **freshly crosses** base-high **fires**; a too-deep
  correction fails on `depth`; **first-cross-not-recross discrimination (R1.M6)** — a planted
  failed-breakout-then-reset where an EARLIER close in the base already exceeded base_high → the later
  recross must NOT fire (`max(close[base_start:asof-1]) <= base_high` is the discriminator; the
  WRONG-PATH one-bar-recross definition wrongly fires); a session already-above-base-high mid-uptrend
  → `no_emergence`; close below base-high → `no_emergence`; a <15-bar base → `duration`; a <40-bar
  slice → `history`; a second base after an earlier qualifying one → `not_primary`; **no-closed-down-swing
  / IPO-day-high fallbacks → `no_base`** (R1.M5). **Depth-ladder boundary tests at the bar boundaries
  (≤25 → 0.25, 26-200 → 0.35, >200 → 0.50)** with a value just over/under each cap. **Calendar→bar
  mapping test (R1.m3):** a base spanning a holiday/weekend gap must gate on *bar* count, not
  `Swing.duration_days` (calendar) — plant a base where the two diverge.
- **timing** — positional window offsets; best-of; no-lookahead per session; **month-precision rows
  are sweep-only** (no single-session recall row, R1.M3) AND use the **full documented-month window**
  (`[first_trading_day_of_month−60bd, last_trading_day_of_month+5bd]`), asserted distinct from the
  parsed-first-of-month `[entry−60bd, entry+5bd]` (R4.m1); day/exact rows use `[entry−60bd, entry+5bd]`.
- **precision_control** — the **own pre-filtered young-window sampler** (R2.M1/R3.M1): asserts the
  eligible candidate pool is `[MIN_HISTORY_BARS−1, MAX_CONTROL_AGE_BARS−1]` (=`[39,503]`) intersected
  with `>=CONTROL_GAP_BARS`-from-entry AND outside `[entry−60bd, entry+5bd]`, sampled deterministically;
  a planted bar beyond `MAX_CONTROL_AGE_BARS` is never eligible (pre-filter, not post-filter); the
  single-session per-anchor rate is the primary estimand, window best-of reported separately (R1.M9).
- **scorecard** — recall/precision + Wilson shape + clustered bootstrap.
- **cohort** — resolves the curated `exemplar_id`s via `exemplar_reader`; rejects an unknown id.
- **CLI** — `ValueError→ClickException`; **ASCII stdout subprocess-through-PowerShell test**.
- **L2-LOCK** — static-import grep + a `sys.modules` import-smoke; **use the hardened, monkeypatch-
  restored pattern, NEVER raw `del sys.modules`** (per the 2026-06-09 xdist module-identity gotcha;
  reproduce isolation issues with `-n 0`, not `-n auto`).

Fixtures: small synthetic OHLCV planted to exercise each criterion + a couple of real-Tiingo slices
from the cohort; derive fixtures from real reader output (shape-drift gotcha).

## 10. Limitations

1. **Tiny n (≈3 evaluable sub-floor: AMZN-1997, BODY, DKS)** — a mechanism-validation proof-of-concept,
   NOT a powered study (R1.M2/M4 shrank it: MELI removed as a young-VCP, JNPR `history`-excluded as
   below Minervini's own ≥2-month minimum). Corpus expansion is the **strongly-advised** immediate
   sequel, not just an optional upgrade.
2. **Thresholds are operationalizations of Minervini's prose** (≥2mo history, 3-5wk base, 25/35/50%
   graduated depth, emergence on close) — documented judgment calls; a sensitivity sweep is future.
3. **Same-ticker control only** — a random-IPO non-leader negative population is the precision rigor
   upgrade (needs IPO-date sourcing + a new Tiingo pull).
4. **#24/#26 OHLCV archive temporal mutation** (Tiingo re-pull drift); split-adjust caveat.
5. **Research-only** — any deployable young-name screen routes through V2.1 §VII.F; promotion gate N/A.
6. **`extract_zigzag_swings` parameterization + "constructive consolidation near ATH"** — the 3%
   zigzag threshold + the swing→base mapping are design choices (pinned at writing-plans). A shallow
   sideways consolidation near the ATH (a valid Ch.11 base) whose pullback is below the zigzag
   threshold yields `no_base` in V1 — a documented limitation; the threshold is a sweepable knob.
7. **Precision estimand** — single-session per-anchor fire rate (primary) and window best-of rate are
   distinct estimands for an event screen and are reported separately, never conflated (R1.M9); the
   same-ticker young-window control measures temporal specificity, not a population base rate.

## 11. Deliverables

- Harness modules (§4) + one CLI registration.
- Method-record stub → `research/method-records/minervini-primary-base-recall.md`.
- Study-design doc → `research/studies/2026-06-09-minervini-primary-base-recall.md`.
- The curated primary-base cohort list (`cohort.py`).
- Outputs → `exports/research/primary-base-recall-<ISO>/`.

## 12. Resolved decisions

| Decision | Resolution |
|---|---|
| Scope | **H1 primary-base screen only** (no young-name H2 stage). |
| Deliverable | **Research recall/precision study** reusing the recall harness; deployment separate (§VII.F). |
| Precision control | **Same-ticker temporal control** (V1); random-IPO control is the rigor upgrade. |
| Cohort size | Ship at the existing cohort (descriptive) — **n≈3 evaluable sub-floor after R1 corrections** (MELI removed, JNPR history-excluded); proof-of-concept, corpus expansion strongly advised. |
| Gate definition | **Minervini Ch.11 primary base** (history ≥2mo, base ≥3wk, graduated depth cap, emergence on close, first-base). |
| Architecture | **Approach A** — new sibling harness over the frozen recall-harness leaves + `foundation` zigzag. |
| Timing | Window-sweep (reliable, all rows; full-calendar-month sweep for month-precision); single-session reported only for day-precision (BODY-only, n=1). Single-session≈sweep is a hypothesis to test, not a guarantee. |
| Stats | Descriptive; **Wilson primary** + exploratory ticker-clustered bootstrap; no inferential claim. |
