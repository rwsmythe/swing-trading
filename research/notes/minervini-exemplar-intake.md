# Minervini correct-entry exemplar — extraction / curation guide

> **Purpose.** Define how the Minervini "correct entry" exemplar set is assembled for the
> *recall / sensitivity* harness, which replays each documented correct entry through our
> screen + filter + detector stack, point-in-time, no lookahead. The exemplar list is the
> binding input — but it is **no longer an operator-transcription bottleneck**: the source
> books are electronic + agent-readable (`reference/books-corpus-index.md`), so **Claude
> extracts candidate exemplars and the operator curates** (accept / reject / adjust).
>
> **Status: intake schema + workflow only.** The arc is NOT commissioned yet — full scope in
> [`docs/minervini-exemplar-recall-commissioning-brief.md`](../../docs/minervini-exemplar-recall-commissioning-brief.md).

---

## Workflow (extraction → curation)

1. **Extract (Claude).** Read the source book `.md` and, for figures whose entry date/price
   live only on the chart, read the figure PNG via vision. Emit one CSV row per *documented
   correct-entry* example into the schema below. **Select, don't dump:** the Minervini books
   contain many charts that are concept illustrations (stage cycles), *failures* (tops, late-stage
   blow-offs), or competitor comparisons — those are NOT correct-entry exemplars. Extract only
   figures/passages that present a buy point / entry the author endorses.
2. **Curate (operator).** Review the extracted CSV: accept / reject / fix the `detector_class`
   mapping, the dates, ambiguous setups. Operator sign-off converts a candidate row to a
   confirmed exemplar (`curated=yes`).
3. **Run (harness, post-Phase-15).** The curated set feeds the recall harness.

**Output file:** `research/data/minervini-exemplars.csv` (gitignored data dir or tracked — TBD at
commissioning; the books themselves are gitignored). The extraction pass generates it in the
schema below; curation edits it in place.

## Source priority

- **PRIME — annotated worked examples:** *Trade Like a Stock Market Wizard* (2013) — dense
  `Figure N.N **TICKER (TKR) YYYY**` captions with setup descriptions; *Think & Trade Like a
  Champion* (2017) — VCP/pivot entries + climax examples. These carry ticker + period + setup in
  text; precise entry date/buy-point often on the chart PNG (read via vision).
- **NOT a worked-example source:** *The Disciplined Swing Trader* (Qullamaggie notes) is
  methodology, not annotated ticker+date entries — excluded from the exemplar set (it informs the
  Qullamaggie KB instead).

---

## Field schema (one row per documented correct-entry example)

Legend: **[required]** harness cannot evaluate without it · **[encouraged]** materially improves
rigor · **[optional]** provenance / interpretation aid.

| Column | Req? | Format | Meaning |
|---|---|---|---|
| `exemplar_id` | **[required]** | slug | Stable id, `<source>-<page>-<ticker>` lowercased — e.g. `twosmw-fig6-5-amgn`. Joins harness results back to the book reference. |
| `ticker` | **[required]** | symbol | The ticker as it trades today. If renamed/delisted (yfinance may not resolve), flag in `notes`. |
| `setup_label` | **[required]** | free text | Minervini's **own** label for the setup, roughly verbatim — `VCP`, `cup-with-handle`, `pivot buy point`, `volatility contraction`, etc. The published interpretation we test recall against. |
| `detector_class` | **[required]** | enum | Mapping to one of our 5 detectors: `vcp` · `flat_base` · `cup_with_handle` · `high_tight_flag` · `double_bottom_w` · `unmapped`. `unmapped` if the setup has no analog (still tests *screening* recall). |
| `entry_date` | **[required]** | `YYYY-MM-DD` | Documented buy / breakout date. Approximate OK; set `date_precision`. From the chart PNG where the text doesn't give it. |
| `buy_point_price` | **[encouraged]** | decimal | Documented pivot / buy-point price if printed. Lets the harness derive the exact entry-crossing session (first session after `base_start_date` with High ≥ buy point). **Split caveat below.** Blank if none. |
| `stop_price` | **[optional]** | decimal | Documented initial stop, if given. Feeds the risk gate precisely; blank → harness synthesizes. |
| `base_start_date` | **[encouraged]** | `YYYY-MM-DD` | Approximate start of the consolidation/base. Lower bound of the window-sweep recall mode; blank → `entry_date − N`. |
| `base_end_date` | **[optional]** | `YYYY-MM-DD` | Approximate base end (often == `entry_date`). |
| `date_precision` | **[optional]** | `exact`\|`day`\|`week`\|`month` | Confidence in `entry_date`; helps interpret near-misses. |
| `source` | **[required]** | code | `TWoSMW` · `THINK_TRADE` · (others as needed). |
| `page` | **[encouraged]** | text | Page and/or figure number — `p.112 fig 6.5`. |
| `extracted_by` | **[required]** | `claude`\|`operator` | Who produced the row. |
| `curated` | **[required]** | `yes`\|`no` | Operator-confirmed (`yes`) vs awaiting review (`no`, default for fresh extractions). |
| `notes` | **[optional]** | free text | Caveats: ticker rename, split, the figure caption, why a `detector_class` mapping, ambiguity. |

---

## Conventions & gotchas

1. **Split / dividend adjustment (important).** yfinance returns **back-adjusted** prices, so a
   pre-split nominal buy point in the book won't match the bars. For split-affected exemplars:
   transcribe the split-adjusted-equivalent, OR leave `buy_point_price` blank and rely on
   `entry_date` + `base_start_date`; note the split. The harness sanity-checks a transcribed buy
   point against the as-of-date bar range and falls back to date-anchoring (with a warning) if it's
   wildly off.
2. **Historical depth.** Pre-2021 exemplars need a deep OHLCV pull (`period="max"`, gotcha #29).
3. **Approximate dates are fine** — recall test, not a backtest. The window-sweep mode absorbs date
   imprecision; that's why both single-session and window-sweep are run.
4. **Extract the setup as the book frames it** — record the author's label; let the harness report
   whether our detector agrees. A documented setup our detector misses is the finding we want.
5. **Source-of-truth corrections.** A later fix to an extracted row routes through the V2.1 §VII.F
   protocol at study time (a method-record note), not a silent edit.

---

## What the harness does with this (preview)

Per exemplar, in **two timing modes** (single breakout session + window-sweep across the base):
record the **bucket** (`aplus`/`watch`/`skip`) from `bucket_for`, the **per-gate pass/fail**
scorecard (which of the 18 A+ gates rejected), and which of the **5 detectors fired** + whether the
fired class matched `detector_class`. A pass = our gates would have surfaced the setup; a miss
localizes the silently-rejecting gate. (Recall scorecard defined in the commissioning brief.)
