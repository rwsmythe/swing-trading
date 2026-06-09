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

Documented examples (Ch.11 + figure captions): AMZN-1997, YHOO, JNPR, DKS, iRobot; MELI and BODY are
named primary bases elsewhere in the book.

## 3. Cohort (honest n ≈ 6 — descriptive/illustrative)

Only names Minervini **frames as a primary base** belong (a young *VCP* like QSII is a category
mismatch and is out of scope). Curated `exemplar_id`s (resolved from
`research/data/minervini-exemplars.csv` via the recall harness's `exemplar_reader`):

| exemplar_id | ticker | role | bars at entry |
|---|---|---|---|
| `twosmw-fig11-1-amzn` | AMZN-1997 | sub-floor (the gap) | ~75 |
| `twosmw-fig11-7-jnpr` | JNPR | sub-floor | ~25 |
| `twosmw-fig10-33-meli` | MELI | sub-floor (book primary base) | ~85 |
| `ttlc-fig10-1-body` | BODY | sub-floor (book primary base) | ~50 |
| `twosmw-fig11-6-dks` | DKS | sub-floor (book primary base; CSV maps dbw) | ~120 |
| `twosmw-fig11-3-yhoo` | YHOO | **sufficient-history positive control** | ~290 |

**5 sub-floor + 1 control = n≈6.** All have Tiingo coverage of their entry era (verified in the CSV
notes). **n is tiny → descriptive + Wilson, no inferential claim.** Corpus expansion
(Google/Starbucks/Reebok/MSFT/Intel/Rambus/RIMM primary bases) is the named rigor upgrade, declined
for V1. QSII and other young-but-not-primary-base names are a *different* (young-VCP) gap, out of scope.

## 4. Architecture — Approach A (new sibling harness over frozen leaves)

`research/harness/minervini_primary_base_recall/`. The shipped `minervini_exemplar_recall` harness
stays **frozen**; this arc imports its reusable leaves. **L2 LOCK** held: imports none of yfinance /
schwabdev / `swing.integrations.schwab` / `swing.data.ohlcv_archive`. The only `swing/` change is the
one CLI registration. **No production DB** (the screen is pure on bars; no equity, no stage).

| Module | Responsibility |
|---|---|
| `primary_base_screen.py` | `PrimaryBaseVerdict` + `screen_at(bars, asof_date)` — the Ch.11 criteria over `extract_zigzag_swings`. |
| `cohort.py` | The curated documented-primary-base `exemplar_id` list (§3) + per-id book citation; resolves rows via `exemplar_reader`. |
| `timing.py` | Single-session + window-sweep `[entry−60bd, entry+5bd]` best-of over `screen_at`. |
| `precision_control.py` | Reuse `control_cohort.sample_control_anchors`; run the screen at control anchors, both modes. |
| `scorecard.py` | Recall + precision + Wilson + ticker-clustered bootstrap, both timing modes. |
| `output.py` / `run.py` | `results.csv` / `per_session.csv` / `summary.md` / `manifest.json` + one CLI reg. |

**Reuse (frozen leaves), verified seams:**
- `minervini_exemplar_recall.ohlcv_reader` — `read_full(symbol, *, tiingo_dir)`, `slice_to(bars, asof_date)`, `read_sliced(symbol, asof_date, *, tiingo_dir, min_bars)`.
- `minervini_exemplar_recall.exemplar_reader` — `read_exemplars(csv_path) -> list[ExemplarRow]` (`exemplar_id, ticker, tiingo_symbol, entry_anchor, date_precision, …`).
- `minervini_exemplar_recall.control_cohort` — `sample_control_anchors(bars, entry_anchor, *, k, window_back, window_fwd) -> list[ControlAnchor(session, session_pos)]`.
- `minervini_exemplar_recall.scorecard` — `wilson_interval(successes, n, z=1.96)`, `ticker_clustered_bootstrap(rows, value_fn, *, b, base_seed)`.
- `swing.patterns.foundation` — `extract_zigzag_swings(bars, initial_threshold_pct, monotonic_narrow=False) -> list[Swing]` (the exact `Swing` field access pinned at writing-plans).

## 5. The primary-base screen (`primary_base_screen.py`)

`screen_at(bars, asof_date) -> PrimaryBaseVerdict` — bars sliced `<= asof_date` (point-in-time; the
first available bar is the IPO proxy). **"Fired" = a buyable primary-base emergence**, all criteria
holding:

1. **History gate** — `len(bars) >= MIN_HISTORY_BARS` (=40, ~2 months). Below → not-yet-evaluable.
2. **Base identification** — `extract_zigzag_swings(bars, ZIGZAG_THRESHOLD_PCT=3.0)`: the highest
   swing-high since IPO (pre-base peak), the down-swing (correction), the consolidation low. Base
   spans `[pre-base-peak → asof]`.
3. **Base duration** — `>= MIN_BASE_BARS` (=15, "at least three to five weeks").
4. **Correction depth ≤ graduated cap** — max drawdown (base-high → base-low) ≤ a duration-graduated
   cap `DEPTH_CAP_BY_DURATION`: `<=40 bars (~8wk): 0.25`, `41-126 (~6mo): 0.35`, `>126 (~1yr+): 0.50`.
5. **Emergence to new high ground — a FRESH crossing event, not a state** — the close crosses above
   `base_high` for the first time at `asof`: `close[asof-1] <= base_high < close[asof]`. This is the
   breakout *bar* (the documented first-close-above-pivot entry), NOT "currently above base_high" —
   the latter would fire across the whole post-breakout uptrend and wreck precision. (No-lookahead
   holds; only `asof` and `asof-1` are read.) The window-sweep provides temporal slack for
   coarse-precision entries; single-session must land on the actual cross bar.
6. **Primary = first base** — no earlier qualifying ≥`MIN_BASE_BARS` consolidation exists in the
   post-IPO history before this one.

`PrimaryBaseVerdict`: `fired: bool` + diagnostics (`base_start_date`, `base_high`,
`correction_depth_pct`, `base_duration_bars`, `emergence_close`) + **`first_rejecting_criterion`** when
not fired (one of `history` / `no_base` / `duration` / `depth` / `no_emergence` / `not_primary`) — the
localizer. All thresholds are documented module constants citing Ch.11.

**Structural note (vs the recall arc):** this is an **emergence/breakout** screen — it fires *at* the
breakout, not during the coil (unlike VCP). So **single-session-at-entry is the correct timing** here
(the documented entry *is* the emergence); the window-sweep mainly absorbs date imprecision. Expect
single-session and window-sweep to be *close*, not divergent.

## 6. Recall + precision measurement

- **Recall (cohort).** Per exemplar: **single-session** `screen_at(≤entry_anchor, entry_anchor)`;
  **window-sweep** `screen_at` over `[entry−60bd, entry+5bd]` (positional, start clamped to 0),
  fired-at-any best-of, firing session(s) recorded. Recall = `N(fired)/N` per mode. **Stratified:**
  the 5 sub-floor names vs YHOO (sufficient-history positive control — the screen *should* fire on a
  known full-history primary base). Per-miss `first_rejecting_criterion`.
- **Precision (same-ticker temporal control).** `sample_control_anchors` (K random sessions
  ≥120bd from entry, outside the sweep window, deterministic seed); run `screen_at` at each in **both**
  timing modes (mode-to-mode). Contrast: exemplar fire rate at the documented emergence vs control
  fire rate at random young-stock sessions of the same names.

## 7. Scorecard (`scorecard.py`)

Computed for both timing modes (reuse recall-harness primitives):
- **Recall** = `N(fired)/N` (sub-floor cohort), + the YHOO positive control reported separately.
- **Wilson 95%** (primary) on the recall fraction; **ticker-clustered bootstrap** (exploratory, marked).
- **Per-criterion first-rejection histogram** across misses (the localizer).
- **Precision contrast** — exemplar vs same-ticker control fire rate, both modes.
- Descriptive; **n≈6 → no inferential claim.**

## 8. Outputs + CLI

- `exports/research/primary-base-recall-<ISO>/`: `results.csv` (per exemplar×mode: fired,
  `first_rejecting_criterion`, base diagnostics, data source), `per_session.csv` (sweep drill-down),
  `summary.md` (recall + precision + Wilson + criterion histogram + YHOO control), `manifest.json`
  (cohort, thresholds with Ch.11 citations, control params + seed, n, per-exemplar provenance,
  `l2_lock_preserved`, UTC timestamps). **ASCII-only.** `.gitignore` allowlist mirrors the
  minervini-recall outputs (track `summary.md`/`manifest.json`/`results.csv`/`per_session.csv`).
- **CLI:** `swing diagnose primary-base-recall` (mirror `minervini-recall`; **no `--db`**; flags
  `--exemplars-csv --tiingo-dir --output-dir --window-back 60 --window-fwd 5 --control-k 5
  --bootstrap-b 2000 --only`); `ValueError → click.ClickException`.

## 9. Testing (TDD per task)

- **primary_base_screen** — one discriminating test per criterion, each with `WRONG-PATH`/`RIGHT-PATH`
  values: a planted primary base whose close **freshly crosses** base-high **fires**; a too-deep
  correction fails on `depth` (e.g. 30% drawdown in a 4-week base → reject; 20% → pass); **fresh-cross
  discrimination** — `close[asof-1] <= base_high < close[asof]` fires, but a session already-above
  base-high (`close[asof-1] > base_high`, mid-uptrend) → `no_emergence` (the WRONG-PATH "state"
  definition would wrongly fire here), and close still below base-high → `no_emergence`; a <3-week
  base fails on `duration`; a <40-bar slice → `history`; a second base after an earlier qualifying one
  → `not_primary`. Graduated-depth boundary tests (25%/35%/50% by duration).
- **timing** — positional window offsets; best-of; no-lookahead per session.
- **precision_control** — reuse the sampler; screen at controls; deterministic.
- **scorecard** — recall/precision + Wilson shape + clustered bootstrap.
- **cohort** — resolves the curated `exemplar_id`s via `exemplar_reader`; rejects an unknown id.
- **CLI** — `ValueError→ClickException`; **ASCII stdout subprocess-through-PowerShell test**.
- **L2-LOCK** — static-import grep + a `sys.modules` import-smoke; **use the hardened, monkeypatch-
  restored pattern, NEVER raw `del sys.modules`** (per the 2026-06-09 xdist module-identity gotcha;
  reproduce isolation issues with `-n 0`, not `-n auto`).

Fixtures: small synthetic OHLCV planted to exercise each criterion + a couple of real-Tiingo slices
from the cohort; derive fixtures from real reader output (shape-drift gotcha).

## 10. Limitations

1. **Very small n (~5-6)** → descriptive/illustrative only; corpus expansion is the named rigor upgrade.
2. **Thresholds are operationalizations of Minervini's prose** (≥2mo history, 3-5wk base, 25/35/50%
   graduated depth, emergence on close) — documented judgment calls; a sensitivity sweep is future.
3. **Same-ticker control only** — a random-IPO non-leader negative population is the precision rigor
   upgrade (needs IPO-date sourcing + a new Tiingo pull).
4. **#24/#26 OHLCV archive temporal mutation** (Tiingo re-pull drift); split-adjust caveat.
5. **Research-only** — any deployable young-name screen routes through V2.1 §VII.F; promotion gate N/A.
6. **`extract_zigzag_swings` parameterization** — the 3% zigzag threshold + the swing→base mapping are
   design choices; document and pin at writing-plans.

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
| Cohort size | **Ship at the existing ~6** documented primary bases (descriptive); corpus expansion deferred. |
| Gate definition | **Minervini Ch.11 primary base** (history ≥2mo, base ≥3wk, graduated depth cap, emergence on close, first-base). |
| Architecture | **Approach A** — new sibling harness over the frozen recall-harness leaves + `foundation` zigzag. |
| Timing | Single-session + window-sweep `[entry−60bd, entry+5bd]` best-of (single-session is the correct timing for an emergence screen). |
| Stats | Descriptive; **Wilson primary** + exploratory ticker-clustered bootstrap; no inferential claim. |
