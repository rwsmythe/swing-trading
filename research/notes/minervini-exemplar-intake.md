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

## Labels vs. data (important)

The book supplies the **ground-truth LABELS only** — ticker, the date Minervini called the buy
point, and his setup name. No market-data API can supply those (the API doesn't know which day
Minervini judged the pivot). **All OHLCV/price data comes from yfinance/Schwab at harness time**
(the existing point-in-time machinery) — never from the book or its chart images. The book's pivot
price, where stated, is just a **text label / anchor** (used to derive the exact entry-crossing
session against yfinance bars); it is subject to the split-adjustment caveat below and is never a
substitute for the bars.

## Workflow (extraction → curation)

1. **Extract the LABELS (Claude).** Read the source book `.md` and emit one CSV row per *documented
   correct-entry* example into the schema below — ticker, entry date, setup, and (where the text
   states it) the pivot price + base dates. **Select, don't dump:** the books contain many charts
   that are concept illustrations (stage cycles), *failures* (tops, blow-offs), or competitor
   comparisons — those are NOT correct-entry exemplars. Extract only author-endorsed buy points.
2. **Curate (operator).** Review the extracted CSV: accept / reject / fix the `detector_class`
   mapping, dates, ticker-resolution flags, ambiguous setups. Operator sign-off flips a row to
   `curated=yes`.
3. **Run (harness, post-Phase-15).** The curated labels feed the recall harness, which pulls the
   actual OHLCV from yfinance/Schwab and evaluates each exemplar point-in-time.

**Output file:** `research/data/minervini-exemplars.csv` (gitignored data dir or tracked — TBD at
commissioning).

## Source priority

- **PRIME — annotated worked examples:** *Trade Like a Stock Market Wizard* (2013) — dense
  `Figure N.N **TICKER (TKR) YYYY**` captions with setup descriptions; *Think & Trade Like a
  Champion* (2017) — VCP/pivot case studies. These carry ticker + period + setup (and usually the
  exact entry date, often the pivot price) **in the text** — no chart-reading needed; where a date
  is fuzzy the window-sweep mode + the yfinance-derived breakout handle it.
- **NOT a worked-example source:** *The Disciplined Swing Trader* (Qullamaggie notes) is
  methodology, not annotated ticker+date entries — excluded (it informs the Qullamaggie KB).

---

## Field schema (one row per documented correct-entry example)

Legend: **[required]** harness cannot evaluate without it · **[encouraged]** materially improves
rigor · **[optional]** provenance / interpretation aid.

| Column | Req? | Format | Meaning |
|---|---|---|---|
| `exemplar_id` | **[required]** | slug | Stable id, `<source>-<page>-<ticker>` lowercased — e.g. `twosmw-fig10-34-crus`. Joins harness results back to the book. |
| `ticker` | **[required]** | symbol | The ticker as it trades today. If renamed/delisted (won't resolve in yfinance), flag in `notes`. |
| `setup_label` | **[required]** | free text | Minervini's **own** label for the setup, roughly verbatim. The published interpretation we test recall against. |
| `detector_class` | **[required]** | enum | Mapping to one of our 5 detectors: `vcp` · `flat_base` · `cup_with_handle` · `high_tight_flag` · `double_bottom_w` · `unmapped` (no analog → still tests *screening* recall). |
| `entry_date` | **[required]** | `YYYY-MM-DD` | The date Minervini documented as the buy/breakout. From the **book text**; approximate OK (set `date_precision`). |
| `buy_point_price` | **[encouraged]** | decimal | Documented pivot/buy-point price **as printed in the text** (a label, not a data source). Lets the harness derive the exact entry-crossing session against yfinance bars. **Split caveat below.** Blank if not stated. |
| `stop_price` | **[optional]** | decimal | Documented initial stop if given; else harness synthesizes. |
| `base_start_date` | **[encouraged]** | `YYYY-MM-DD` | Approx. start of the consolidation/base (window-sweep lower bound); blank → `entry_date − N`. |
| `base_end_date` | **[optional]** | `YYYY-MM-DD` | Approx. base end (often == `entry_date`). |
| `date_precision` | **[optional]** | `exact`\|`day`\|`week`\|`month` | Confidence in `entry_date`. |
| `source` | **[required]** | code | `TWoSMW` · `THINK_TRADE` · (others as needed). |
| `page` | **[encouraged]** | text | Page / figure number. |
| `extracted_by` | **[required]** | `claude`\|`operator` | Who produced the row. |
| `curated` | **[required]** | `yes`\|`no` | Operator-confirmed vs awaiting review (default `no`). |
| `notes` | **[optional]** | free text | Caveats: ticker rename/delisting, split, the figure caption, mapping rationale, ambiguity. |

---

## Conventions & gotchas

1. **Prices come from yfinance, not the book.** `buy_point_price` is a label/anchor only. yfinance
   bars are **back-adjusted** for splits/dividends, so a pre-split nominal book price won't match —
   for split-affected names, leave `buy_point_price` blank (or note the split) and anchor on
   `entry_date` + `base_start_date`. The harness sanity-checks any `buy_point_price` against the
   as-of-date bar range and falls back to date-anchoring (with a warning) if it's wildly off.
2. **Historical depth.** Pre-2021 exemplars need a deep yfinance pull (`period="max"`, gotcha #29).
3. **Ticker resolution.** Many older exemplars are delisted/renamed (e.g. TASR→AXON; acquisitions).
   yfinance may not resolve them — flag in `notes` for curation.
4. **Approximate dates are fine** — recall test, not a backtest. Window-sweep absorbs imprecision;
   that's why both single-session and window-sweep are run.
5. **Extract the setup as the book frames it** — record the author's label; let the harness report
   whether our detector agrees. A documented setup our detector misses is the finding we want.
6. **Source-of-truth corrections** route through V2.1 §VII.F at study time (a method-record note).

---

## What the harness does with this (preview)

Per exemplar, pulling OHLCV from yfinance, in **two timing modes** (single breakout session +
window-sweep across the base): record the **bucket** (`aplus`/`watch`/`skip`) from `bucket_for`, the
**per-gate pass/fail** scorecard (which of the 18 A+ gates rejected), and which of the **5 detectors
fired** + whether the fired class matched `detector_class`. A pass = our gates would have surfaced
the setup; a miss localizes the silently-rejecting gate. (Recall scorecard defined in the
commissioning brief.)
