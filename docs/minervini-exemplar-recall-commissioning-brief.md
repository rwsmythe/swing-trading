# Minervini correct-entry exemplar recall — commissioning / scoping brief

> **STATUS: PREPARATION ONLY — NOT COMMISSIONED.** Do not begin execution until **Phase 15
> closes** (operator-decided). This brief scopes the arc so the post-Phase-15 copowers cycle
> (brainstorm → writing-plans → executing-plans) starts clean. Research-branch arc (artifacts under
> `research/`; ≤1 CLI registration in `swing/`).

**Backlog source:** `research/phase-0-tasks.md` §"Applied research candidates" — *Minervini
correct-entry exemplar recall / sensitivity validation*.
**Drafted:** 2026-06-05 (orchestrator), grounded in a disk survey of the reusable infra.

---

## 1. The question

Given Minervini's documented **correct-entry** examples, **would our screening + filtering pipeline
have surfaced each one** (landed it in `aplus`/`watch` via `bucket_for`), and **would any of our
indications have fired** (the 5 V1 detectors; the A+/trend-template/VCP gates) — evaluated strictly
**point-in-time, no lookahead**, at/around the entry-crossing session? A **pass** = our gates would
have caught a known-good setup; a **miss localizes the silently-rejecting gate** (trend / VCP /
proximity / risk).

This is a **true-positive RECALL / sensitivity** test (does the pipeline CATCH known-good setups) —
**entry-side**, and **complementary to** (not a repeat of) the closed 2026-05-27 expectancy arc
(which asked whether rulesets *profit*). It is **NOT temporal-log-gated** (it uses Minervini ground
truth, not forward-walk accumulation), so it can run as soon as Phase 15 closes.

> Note: this arc is **entry-focused.** The 2026-06-05 Think & Trade sell-side verification
> (`reference/methodology/minervini-sell-side-rules.md`) is a separate body-of-knowledge thread —
> not part of recall scope.

---

## 2. Premise correction (2026-06-05): exemplar assembly is in-house

The backlog brief assumed the books were physical-only and the binding prerequisite was *operator
transcription*. **That is obsolete** — the source books are transcribed and agent-readable
(`reference/books-corpus-index.md`). So **Claude extracts** candidate exemplars from the book `.md`
(+ figure PNGs via vision for chart-only dates/prices) and **the operator curates** (accept /
reject / fix). Workflow + schema: `research/notes/minervini-exemplar-intake.md`. This removes the
human bottleneck; the exemplar set is no longer a blocking dependency.

---

## 3. Decomposition — two independent evaluation halves (both have reusable point-in-time harnesses)

| Half | Question | Engine | Reuse vehicle |
|---|---|---|---|
| **H1 — screen → bucket** | Would `bucket_for` land it in `aplus`/`watch`? Which of the 18 A+ gates rejected? | `swing/evaluation/evaluator.py:evaluate_one` → `swing/evaluation/scoring.py:bucket_for` (8 trend-template + 9 VCP + 1 risk = 18 gates, each a `Result(name,result)`) | **V2 OHLCV evaluator harness** `research/harness/aplus_v2_ohlcv_evaluator/` (already does no-lookahead `<= asof_date` slice → universe-context rebuild → `evaluate_one`). Seam: replace the cfg-sweep loop with a `(ticker, entry-date)` loop. |
| **H2 — indication → fired** | Did any of the 5 detectors fire (`geometric_score > 0`)? Did the fired class match the documented setup? | `swing/patterns/*` (vcp, flat_base, cup_with_handle, high_tight_flag, double_bottom_w) via `_pattern_detect_registry()` | **Pattern-cohort detector harness** `swing diagnose pattern-cohort-detect` (`research/harness/pattern_cohort_evaluator/`) — built for exactly "feed `(ticker, asof_date)`, run detectors as-of that date, emit fired/not-fired + composite." Cohort CSV needs only `ticker, asof_date` (+ optional `pattern_class_filter`). |

---

## 4. Infra-reuse map (disk-verified)

| Component | Path | Verdict |
|---|---|---|
| `bucket_for` + 18 A+ gates | `swing/evaluation/scoring.py`, `swing/evaluation/criteria/*.py` | **REUSABLE AS-IS** — pure; each gate yields `Result.name`/`.result` → the per-gate scorecard falls out. |
| As-of slice (no lookahead) | `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py` (`<= asof_date`) | **REUSABLE AS-IS.** |
| Universe/RS context rebuild | `…/context_builder.py:build_eval_run_cohort` | **NEEDS ADAPTATION** — see §6 RS note (TT8-allowed-miss simplification). |
| 5 detectors + windows | `swing/patterns/`, `swing/patterns/foundation.py:generate_candidate_windows` (zigzag_pivot) | **REUSABLE AS-IS.** |
| Cohort harness | `research/harness/pattern_cohort_evaluator/run.py:run_harness` | **REUSABLE AS-IS** — emits `results.csv`/`summary.md`/`manifest.json`; `geometric_score>0` = fired. |
| 9-metric scorecard | `research/harness/g2_w_bottom_ruleset_backtest/scorecard.py` | **NOT REUSABLE** — outcome/expectancy-oriented (needs closed P&L). Recall needs a new scorecard (§5). |

---

## 5. The recall scorecard (the one genuinely-new piece — small)

The cited 9-metric scorecard is profit-oriented and does **not** fit a recall test. Define a new,
small recall scorecard:

- **Per-detector recall** — `N(fired for expected class) / N(exemplars)`, per detector + overall.
- **Per-gate pass rate / first-rejection attribution** — across exemplars, the fraction passing each
  of the 18 gates, and for each *missed* exemplar the **first gate that rejected it** (the localizer).
- **Bucket distribution** — how many exemplars reached `aplus` / `watch` / `skip`.
- **Both timing modes reported side-by-side** (§6).

---

## 6. Timing semantics (operator-decided: BOTH, side by side)

Run each exemplar in **two modes** and report together:

- **Single-session** — strict evaluation at the entry-crossing session (derived from `buy_point_price`
  where documented: first session after `base_start_date` with High ≥ buy point; else the documented
  `entry_date`).
- **Window-sweep** — evaluate across a span of sessions from `base_start_date` into the entry; record
  the **best bucket / detector-fired state** reached + per-session detail.

**Rationale:** our VCP gate is designed to fire *during the tight consolidation before* the breakout
(proximity-to-20MA ≤5%, tightness ≤0.67×ADR). At the breakout bar the stock is extended/wide-range,
so VCP4 + VCP7 fail *by design* — single-session would under-count VCP recall. Running both isolates
how much the timing choice matters. (Trend-template gates are timing-insensitive — they pass
throughout the uptrend.)

---

## 7. Exemplar assembly

- **Sources:** *Trade Like a Stock Market Wizard* (2013) — dense `Figure N.N **TICKER (TKR) YYYY**`
  captions with setup descriptions (PRIME) + *Think & Trade Like a Champion* (2017) — VCP/pivot
  entries. **Excluded:** *The Disciplined Swing Trader* (Qullamaggie methodology, not annotated
  ticker+date entries).
- **Select, don't dump:** the books contain many concept-illustration / failure / competitor charts
  that are NOT correct-entry exemplars. Extract only author-endorsed buy points.
- **Schema + workflow:** `research/notes/minervini-exemplar-intake.md`. Output:
  `research/data/minervini-exemplars.csv`.
- **Size:** TBD by the extraction pass (TWoSMW alone has dozens of annotated figures; a subset are
  correct-entry exemplars). Final n drives the bootstrap-vs-statistical framing (§10).

---

## 8. Methodological subtleties / known limitations

1. **Breakout-extension VCP** — see §6 (the reason for dual timing modes).
2. **Split/dividend adjustment** — yfinance bars are back-adjusted; pre-split nominal buy points
   won't match. The harness sanity-checks `buy_point_price` vs the as-of bar range and falls back to
   date-anchoring with a warning.
3. **RS / universe reconstruction at historical dates** — TT8 (RS rank) needs a universe
   cross-section as-of the entry date. **Simplification:** TT8 is in `allowed_miss_names` by default,
   so a valid bucket can be computed with TT8 marked NA as long as the other 7 trend-template gates
   pass — RS reconstruction is **optional for a first pass** (document it as a limitation), with a
   proxy-universe RS as the rigor upgrade. Resolve at brainstorm.
4. **OHLCV archive temporal mutation (#24/#26)** — yfinance re-fetch drifts historical bars; an
   immutable snapshot is the ideal. Characterize as an L6-style limitation.
5. **Historical depth (#29)** — pre-2021 exemplars need `period="max"` (else `sliced=0`).
6. **`current_equity` surrogate** — the risk gate needs equity as-of date; use historical
   `account_equity_snapshots` or the project $7500 floor (flag surrogate use).
7. **`unmapped` setups** — Minervini setups with no analog among our 5 detectors still test
   *screening* recall (bucket) even when no detector can fire.

---

## 9. Disciplines to respect

- Strict **point-in-time / no-lookahead** (the V2 harness's `<= asof_date` slice is the contract).
- **Research carve-out** (V2.1 §IV.D/§VII.C): harness lives at `research/harness/minervini_exemplar_recall/`;
  at most ONE CLI subcommand registration in `swing/cli.py` (mirror `aplus-sensitivity-v2`).
- **Source-of-truth correction protocol (V2.1 §VII.F)** — any deployable finding (e.g. a gate
  re-tune) routes through it, not a direct patch.
- Brief-authoring family #33–#37; #24/#26 archive-freshness; #29 historical depth.

---

## 10. Open questions for the brainstorm (post-Phase-15)

1. **Baseline / null hypothesis for recall** — recall vs *what*? (e.g. detector confirmation rate on
   production `aplus` candidates; or simply "≥X% of documented exemplars surfaced.")
2. **RS reconstruction** — TT8-NA first pass (documented limitation) vs proxy-universe RS (rigor)?
3. **Template-match Pass 2** — run `--template-match on` (composite) or geometric-only for the recall
   signal?
4. **Window-sweep aggregation** — exact "best over window" rule + window length (`base_start_date` →
   entry; default `N` when base undated).
5. **Exemplar-table promotion** — keep the curated set as CSV, or also load into `pattern_exemplars`
   (heavier; only needed if we want template-matching against them)?
6. **Sizing/framing** — once n is known, bootstrap (small-n, descriptive) vs any inferential claim.

---

## 11. Proposed deliverables at commissioning (copowers cycle)

- **Method-record stub** → `research/method-records/minervini-exemplar-recall.md` (per `_template.md`).
- **Study design** → `research/studies/<YYYY-MM-DD>-minervini-exemplar-recall.md` (per the
  `earnings-proximity-exclusion.md` / `2026-05-24-pattern-cohort-detection.md` precedent).
- **Harness** → `research/harness/minervini_exemplar_recall/` (extraction/loader + dual-mode evaluator
  wrapping the two reuse vehicles + the recall scorecard + `output.py`) + ≤1 CLI registration.
- **Curated exemplar CSV** → `research/data/minervini-exemplars.csv` (extraction → operator curation).
- Outputs → `exports/research/minervini-exemplar-recall-<ISO>/` (`results.csv`/`summary.md`/`manifest.json`).

---

## 12. Status / dependencies

- **Gating:** start AFTER Phase 15 closes (operator-decided). Not temporal-log-gated.
- **Inputs ready:** the two reuse harnesses (verified), the electronic book corpus (complete), the
  intake schema + extraction workflow.
- **Prep remaining before commissioning:** (optional) a small **proof-of-extraction** (5–10 real
  exemplars) to validate the schema + the figure-vision date/price extraction end-to-end.
