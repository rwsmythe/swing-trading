# Session-snapshot scripts

These scripts reproduce specific historical research-branch sessions. They are
NOT the canonical interface for running the harness — that is
`python -m research.harness.earnings_proximity.run` per the parent README.
These exist for procedural reproducibility of committed evidence summaries.

## Sessions captured

- **session2c_*.py** — Session 2c (committed 2026-04-24, evidence summary at
  `../../../studies/earnings-proximity-exclusion-results.md`). Reproduces the
  metrics in commit `e5510a8`'s `analysis_summary.json` against the cache
  state at `~/swing-data/research-cache/`.

  Note: `session2c_run_full_study.py` includes a per-ticker
  `dropna(subset=["Open","High","Low","Close"])` preprocess that was a
  session-level workaround for pre-IPO NaN padding from yfinance batch
  output. The permanent harness fix landed in commit C3 of the post-Session-2c
  housekeeping bundle (`fetchers.load_ohlcv` / `load_ohlcv_with_stats` now
  drop pre-IPO NaN rows internally), so future runs do not need this
  preprocess. The script keeps the preprocess for byte-identity with the
  Session 2c run; on a post-fix harness it is a redundant no-op.

## Intended invocation

Cache warm-up (re-runs of Session 2c only — once the cache is warm you can
skip this step on subsequent reruns):

```bash
python -m research.harness.earnings_proximity.scripts.session2c_warm_cache
```

Full study run (writes `outcomes.csv`, `variant_membership.csv`,
`metrics.csv`, `run_manifest.json` to `--output-dir`; default matches
Session 2c's path `research/harness/earnings_proximity/full-run-out/`):

```bash
python -m research.harness.earnings_proximity.scripts.session2c_run_full_study \
    --output-dir research/harness/earnings_proximity/full-run-out/
```

Confidence-interval summary (reads the artifacts written by the previous
step and produces `analysis_summary.json` in the same directory):

```bash
python -m research.harness.earnings_proximity.scripts.session2c_compute_cis \
    --input-dir research/harness/earnings_proximity/full-run-out/
```

## Reproducibility expectation

Running `session2c_run_full_study.py` against the same cache state SHOULD
reproduce the per-variant metrics in commit `e5510a8`'s `metrics.csv` and
`analysis_summary.json` for deterministic fields:

- `signal_count`, `traded_count`, `dropped_count`, `stopped_count`,
  `gapped_count`, `expectancy_r` — fully deterministic given a fixed
  cache + fixed harness code.
- `expectancy_ci95`, `expectancy_delta_ci95` — deterministic given fixed
  bootstrap seed (`20260424`) and fixed `n_resamples` (10000), per
  `analysis_summary.json.bootstrap_config`.
- `gap_through_rate_wilson_ci95`, `gap_rate_diff_newcombe_ci95_pp` —
  closed-form given fixed Wilson/Newcombe formulas.

If the reconstruction does not produce byte-identical output against
commit `e5510a8`, that is a finding worth investigating before trusting
the script for any further use. Known caveat: this reconstruction was
written from Session 2c's documented artifacts (analysis_summary.json,
outcomes.csv, variant_membership.csv, the harness's
`run_replay()` API surface, and the brief's textual description) rather
than from the deleted originals. Minor numerical drift may exist in
non-load-bearing fields (e.g., float-formatting precision); the
deterministic fields listed above should match exactly. **The
reconstructed scripts have not been re-executed against the live cache as
part of the C2 commit** (it would re-fetch and consume yfinance quota for
no analysis benefit); operators rerunning Session 2c should treat the
first run's diff against `e5510a8` as part of validating the
reconstruction.
