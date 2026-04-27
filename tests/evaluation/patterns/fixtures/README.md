# Chart-Pattern Flag-V1 Labeled Fixtures

## 1. Purpose

This directory holds **operator-labeled OHLCV fixtures** for the chart-pattern
flag-v1 integration test suite (`tests/evaluation/patterns/test_flag_classifier_integration.py`).

Per spec §4.2 (`docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`),
the **operator (Reid Smythe) is the SOLE labeler** in V1. There is no
second-labeler cross-check and no inter-rater reliability metric. The labels
encoded here are the operator's qualitative chart-reading calls; they are the
ground truth that the classifier (`classify_flag(bars)`) is evaluated against.

The label is the operator's qualitative call — the algorithm's actual gate
evaluation is the test under test, NOT the label generator.

## 2. File format (paired CSV + JSON)

Each fixture is a **pair** of files sharing a stem:

```
<TICKER>_<YYYY-MM-DD>_<label>.csv    ← OHLCV bars (literal yfinance pull; ~63 trading days via period='90d')
<TICKER>_<YYYY-MM-DD>_<label>.json   ← {label, notes, expected_confidence_min?}
```

Where:
- `<TICKER>` is the ticker symbol (e.g., `AAPL`).
- `<YYYY-MM-DD>` is the **end date** of the 60-bar window (the right edge of the
  chart the operator was reading).
- `<label>` is `flag` or `none` (must match the JSON `label` field; embedded in
  the filename for at-a-glance inventory).

### CSV format

The CSV is the **literal yfinance OHLCV pull** — the unmodified output of
`yfinance.Ticker(...).history(...).to_csv(...)`. Standard columns: `Open`,
`High`, `Low`, `Close`, `Volume`, with a `Date` index (yfinance also emits
`Dividends` and `Stock Splits`; preserve them as-is).

**DO NOT hand-edit values.** Fixtures must be reproducible from a yfinance
refresh of the same `(ticker, end_date)` pair.

### JSON schema

```json
{
  "label": "flag",
  "notes": "Tight pullback (~5%) after ~25% pole; ma_structure clean; gates 4/6/7/8/9 visually pass.",
  "expected_confidence_min": 0.65
}
```

| Field                       | Type            | Required | Description                                                                                                                       |
|-----------------------------|-----------------|----------|-----------------------------------------------------------------------------------------------------------------------------------|
| `label`                     | `"flag"` \| `"none"` | yes  | The operator's call.                                                                                                              |
| `notes`                     | string          | yes      | Operator rationale: which gate(s) the fixture exercises (e.g., "wide-and-loose, fails tightness").                                |
| `expected_confidence_min`   | float in [0, 1] | optional | For `flag` fixtures only. Pins a confidence floor — test asserts `result.confidence >= expected_confidence_min`.                  |

## 3. Labeling rules (per spec §4.2)

- **Labeler.** The operator (Reid Smythe) is the sole labeler in V1. No
  second-labeler cross-check; no inter-rater reliability metric.
- **Rubric.** Spec §3.1.3's 11 gates + the reference image at
  `reference/images/flag_pattern.png`. A bar set qualifies as a `flag` label
  iff the operator chart-reads it and judges (a) the visual pattern matches a
  flag per the reference image, AND (b) at least four of gates 4 / 6 / 7 / 8 / 9
  visually appear to clear (i.e., the operator's eye agrees with the
  algorithm's intent without literally computing each gate).
- **Procedure.** Operator picks `(ticker, ending-date)` pairs from chart-reading
  sessions, fetches OHLCV via yfinance into a 60-bar window ending at the
  chosen date, labels each as `flag` or `none`, captures notes (e.g.,
  "wide-and-loose, fails tightness"), saves CSV + JSON to this directory.
- **`notes` field convention.** Record WHICH gate(s) the operator believes the
  fixture exercises. For `flag` fixtures, list the gates that visually pass
  (subset of 4/6/7/8/9). For `none` fixtures, list the gate(s) that visually
  FAIL — this is what makes the fixture useful as a rejection-case probe.
- **Disagreement resolution.** N/A in V1 (single labeler).

## 4. Coverage requirement

Per spec §4.2, the V1 floor is **≥15 total fixtures = 8 flags + 7 non-flags**.
The non-flag set must span the rejection cases enumerated in spec Q2:

| Rejection case               | Failing gate(s) (informational)         |
|------------------------------|-----------------------------------------|
| Wide-and-loose               | tightness or pullback_depth             |
| Deep base / cup              | flag_length range                       |
| Sideways drift, no pole      | pole_gain                               |
| Late-stage failed breakout   | flag_floor_holds                        |
| Stage-4 with bounce          | ma_structure                            |
| Multi-month flat base        | flag_length range                       |
| Ambiguous edge case          | operator's call on which gate           |

Aim for one fixture per rejection case (7 non-flags total). The eight `flag`
fixtures should span varied tickers / sectors / market regimes — not eight
near-identical examples from one rally.

## 5. Immutability

**Fixtures are immutable once committed.** This is anti-rationalization
discipline (analogous to `hypothesis_label`): you must not rewrite history to
match the algorithm's behavior.

- **NEVER edit a fixture's CSV or JSON in place.**
- If a label later turns out to be wrong (operator changed their mind on
  re-review), **retire the fixture**: delete both the CSV and JSON, commit the
  deletion, and add a new fixture under a **different end-date** (e.g., the
  next-or-prior trading day's 60-bar window). Never add a `_v2`-style version
  suffix on the ticker — the filename schema `<TICKER>_<YYYY-MM-DD>_<label>`
  reserves the underscore as the field separator, and a versioned suffix
  corrupts the at-a-glance inventory schema.
- Bug-fix to a corrupted CSV (e.g., yfinance returned partial data the day it
  was pulled) is also a retire-and-replace, not an edit-in-place.

Why: the integration suite is the discipline check on the classifier. If
fixtures drift in response to algorithm changes, the suite stops being a
discipline check and starts being a rubber stamp.

## 6. Generation procedure (operator-facing)

1. **Pick a `(ticker, end_date)` pair** from a chart-reading session. The
   end-date is the right edge of the 60-bar window — typically a recent
   completed session for live work, or a historical date for backfill.

2. **Pull the yfinance bars and save the CSV.** From the repo root:

   ```bash
   python -c "import yfinance as yf; df = yf.Ticker('AAPL').history(end='2026-04-26', period='90d'); df.to_csv('tests/evaluation/patterns/fixtures/AAPL_2026-04-26_flag.csv')"
   ```

   `period='90d'` yields ~63 trading days of data, comfortably above the
   classifier's 36-bar minimum (`MIN_BARS=36` in
   `swing/evaluation/patterns/flag_classifier.py`). The helper passes the full
   window through to `classify_flag`; the classifier searches anchor positions
   over the available bars and does not require pre-trimming.

3. **Author the paired JSON** alongside the CSV. Same stem, `.json` extension.
   At minimum: `label` and `notes`. Include `expected_confidence_min` for
   `flag` fixtures if you want to pin a confidence floor.

4. **Verify the pair.** Open the CSV in a spreadsheet or chart tool and
   confirm the visual pattern matches the label. The bar at index `-1` should
   correspond to your chosen end-date (subject to yfinance's session
   semantics — if the date is a non-trading day, expect the prior session).

5. **Commit.** Conventional message:

   ```
   test(patterns): add labeled flag fixture <TICKER>_<DATE>
   ```

   Or for non-flag:

   ```
   test(patterns): add labeled non-flag fixture <TICKER>_<DATE> (<rejection-case>)
   ```

## 7. Running the integration tests

```bash
python -m pytest tests/evaluation/patterns/test_flag_classifier_integration.py -v
```

Behavior:
- **Empty fixtures directory** (only `.gitkeep` + this `README.md`) → suite
  **SKIPS gracefully**. This is the bootstrap state.
- **With committed fixtures** → suite parametrizes one test case per fixture,
  loads the CSV via the helper module, runs `classify_flag(bars)`, and asserts:
  - For `label == "flag"`: `result.pattern == "flag"`, and if
    `expected_confidence_min` is set, `result.confidence >= expected_confidence_min`.
  - For `label == "none"`: `result.pattern in ("none", None)` (accepts both the
    evaluated-negative sentinel `"none"` and the system-error sentinel `None`
    defensively).

If a fixture starts failing after a classifier change, the operator must
either (a) accept the failure as a regression and revert/fix the classifier,
or (b) decide on re-review that the original label was wrong — in which case
**retire-and-replace** the fixture per §5, never edit-in-place.

## FP-biased tuning (spec §4.2)

If integration tests show false-positives outweigh false-negatives, tighten
defaults (raise `pole_gain`, lower `pullback`, lower `tightness` ratio).
Tuning history is captured in the spec or per-phase notes, not in this README.
